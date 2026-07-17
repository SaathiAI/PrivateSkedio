"""
vector_store.py — Pinecone behavioral memory for SkedioAI
=======================================================

This file is the retrieval-oriented memory layer, not the structured source of truth.

Three namespaces, three purposes:

  context   -> learner-model memory records (REWRITE on update, never append)
               "prefers shorter sessions", "late nights often fail after tuition"

  episodic  -> append-only event log, never deleted
               "completed covalent bonding, 1.75h, Thursday"
               snapshot before every destructive change

  backlog   -> one entry per incomplete TOPIC (not subtopic)
               REWRITE on update, never append
               metadata carries subtopics list for LLM-readable summaries

Critical invariant:
- Neo4j is the structured source of truth.
- Pinecone is written after durable graph updates succeed.
- Agents retrieve from Pinecone for context and memory, not for authoritative truth.
"""

import hashlib
import os
import json
import uuid
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

from pinecone import Pinecone
from langchain_google_genai import GoogleGenerativeAIEmbeddings

logger = logging.getLogger(__name__)

os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
os.environ.setdefault("LANGCHAIN_PROJECT", "skedioai-memory")
os.environ.setdefault("LANGCHAIN_API_KEY", os.getenv("LANGCHAIN_API_KEY", ""))
os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")

EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_DIM = 3072
INDEX_NAME = "saathi-class-10"
BACKLOG_NAMESPACE = "chapter_backlog_v2"

EPISODIC_EVENT_TYPES = {
    "session_complete",
    "session_partial",
    "session_skipped",
    "session_progress",
    "session_undo",
    "subtopic_complete",
    "subtopic_undo",
    "plan_created",
    "plan_rescheduled",
    "plan_deleted",
    "task_restarted",
    "plan_snapshot",
    "clash_detected",
    "clash_resolved",
    "clash_escalated",
    "life_event",
    "subtopic_completion",
    "skip",
    "plan_complete",
    "plan_delete",
    "struggle_signal",
}


class VectorStore:
    """Pinecone memory layer for semantic retrieval.

    Three namespaces, three purposes:
      context  -> learner-model memory (REWRITE per kind, never append)
      episodic -> what happened (APPEND only, never delete)
      backlog  -> what's unfinished (REWRITE per match_key)

    Usage:
        vs = VectorStore()
        await vs.log_event(user_id, event_type, text, metadata)
        memory = await vs.load_full_memory(user_id)

    Critical invariant: Neo4j is the source of truth. Pinecone is
    written after graph updates succeed, never before.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(VectorStore, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._pinecone_client: Optional[Pinecone] = None
        self._index = None
        self._search_cache: dict[tuple, list[dict]] = {}
        self._initialized = True

    # ── internal helpers ────────────────────────────────────────────────────────
    # These keep vector IDs, metadata normalization, and index access
    # consistent across the three namespaces.

    def _get_index(self):
        """Lazy-init Pinecone index connection."""
        if self._index is None:
            self._pinecone_client = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
            self._index = self._pinecone_client.Index(INDEX_NAME)
        return self._index

    def _backlog_vector_id(self, user_id: str, match_key: str) -> str:
        """Deterministic vector ID for a backlog entry (one per user+topic)."""
        digest = hashlib.md5(match_key.encode()).hexdigest()
        return f"{BACKLOG_NAMESPACE}:{user_id}:{digest}"

    def _vector_id(self, namespace: str, key: str, data: Optional[dict] = None) -> str:
        """Build vector ID — uses special backlog format if applicable."""
        user_id = (data or {}).get("user_id")
        if namespace == BACKLOG_NAMESPACE and user_id:
            return self._backlog_vector_id(user_id, key)
        return f"{namespace}:{key}"

    @staticmethod
    def _json_list(value) -> list:
        """Safely parse a value into a list. Handles str, list, or None."""
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, list) else []
            except Exception:
                return []
        return []

    def _normalize_backlog_metadata(self, metadata: dict) -> dict:
        """Normalize backlog metadata from Pinecone into consistent fields.

        Pinecone stores JSON strings for list fields. This method parses
        them and ensures subtopics, completed, and pending are always lists.
        """
        item = dict(metadata or {})
        subtopics = self._json_list(item.pop("subtopics_json", None)) or self._json_list(
            item.get("subtopics")
        )
        completed = self._json_list(
            item.pop("subtopics_completed_json", None)
        ) or self._json_list(item.get("subtopics_completed"))
        pending = (
            self._json_list(item.pop("subtopics_pending_json", None))
            or self._json_list(item.pop("subtopics_remaining_json", None))
            or self._json_list(item.get("subtopics_pending"))
            or self._json_list(item.get("subtopics_remaining"))
        )
        content_keys = self._json_list(
            item.pop("content_match_keys_json", None)
        ) or self._json_list(item.get("content_match_keys"))

        item["subtopics"] = subtopics
        item["subtopics_completed"] = completed
        item["subtopics_pending"] = pending
        item["content_match_keys"] = content_keys
        return item

    async def embed(self, text: str) -> list[float]:
        """Embed text using Gemini embedding-001 (3072 dim) - cached client."""
        from src.database.client_cache import get_embedding_client

        embeddings = get_embedding_client()
        return await embeddings.aembed_query(text.strip())

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        from src.database.client_cache import get_embedding_client

        embeddings = get_embedding_client()
        return await embeddings.aembed_documents([t.strip() for t in texts])

    async def _query_index(self, **kwargs):
        """Run Pinecone's blocking query API without blocking the event loop."""

        index = self._get_index()
        return await asyncio.to_thread(index.query, **kwargs)

    # ── context namespace ─────────────────────────────────────────────────────
    # Context stores lean learner-model records. Low-churn memory that gets
    # rewritten per kind, never appended.

    async def vector_filter(self, subject: str = None, chapter_status: str = None):
        """Filter syllabus chapters by subject and/or status.

        Uses a zero vector since we're filtering, not searching semantically.
        Returns a formatted string of matching chapters.
        """

        pinecone_filter = {}

        if subject:
            pinecone_filter["subject"] = {"$eq": subject}

        if chapter_status:
            pinecone_filter["chapter_status"] = {"$eq": chapter_status}

        try:
            index = self._get_index()

            results = index.query(
                vector=[0.001] * EMBEDDING_DIM,
                filter=pinecone_filter,
                top_k=50,
                namespace="syllabus",
                include_metadata=True,
            )

            if not results.get("matches"):
                return "No chapters found matching those exact filters."

            chapter_list = []
            for match in results["matches"]:
                meta = match["metadata"]
                name = meta.get("chapter_name", "Unknown")
                marks = meta.get("chapter_weightage_marks", 0)
                chapter_list.append(f"- {name} ({marks} marks)")

            return "Here are the matching chapters:\n" + "\n".join(chapter_list)

        except Exception as e:
            return f"Error executing database filter: {str(e)}"

    async def list_syllabus_by_subject(
        self,
        subject: str,
        chapter_status: str | None = None,
        top_k: int = 50,
    ) -> list[dict]:
        """Fetch syllabus entries by metadata only, without Gemini embeddings.

        This is the reliable path for whole-subject syllabus lookups and exact
        chapter filtering. Semantic search can still exist as a fallback, but
        basic curriculum truth should not depend on an embedding API call.
        """

        pinecone_filter = {"subject": {"$eq": subject}}
        if chapter_status:
            pinecone_filter["chapter_status"] = {"$eq": chapter_status}

        try:
            index = self._get_index()
            results = await asyncio.wait_for(
                asyncio.to_thread(
                    index.query,
                    vector=[0.001] * EMBEDDING_DIM,
                    filter=pinecone_filter,
                    top_k=top_k,
                    namespace="syllabus",
                    include_metadata=True,
                ),
                timeout=10,
            )

            return [
                {**m.metadata, "score": m.score}
                for m in results.matches
                if m.metadata
            ]
        except Exception as e:
            logger.error(
                "[syllabus] metadata fetch failed for subject=%r status=%r: %r",
                subject,
                chapter_status,
                e,
            )
            return []

    async def get_all_context(self, user_id: str) -> list[dict]:
        """Fetch all context facts for a user (used by load_full_memory)."""
        try:
            index = self._get_index()
            dummy_vector = [0.0] * EMBEDDING_DIM

            results = index.query(
                vector=dummy_vector,
                top_k=20,
                namespace="context",
                filter={"user_id": {"$eq": user_id}},
                include_metadata=True,
            )
            return [m.metadata for m in results.matches if m.metadata]

        except Exception as e:
            logger.error(f"[context] get_all failed: {e}")
            return []

    async def list_learner_memory(self, user_id: str) -> list[dict]:
        """Return lean learner-memory records sorted for inspection."""

        items = await self.get_all_context(user_id)
        return sorted(
            items,
            key=lambda item: (
                str(item.get("kind") or "zzz"),
                str(item.get("updated_at") or ""),
                str(item.get("memory_id") or ""),
            ),
        )

    async def search_context(
        self, user_id: str, query: str, top_k: int = 5
    ) -> list[dict]:
        """Semantic search over context facts for a user."""
        try:
            index = self._get_index()
            vector = await self.embed(query)

            results = index.query(
                vector=vector,
                top_k=top_k,
                namespace="context",
                filter={"user_id": {"$eq": user_id}},
                include_metadata=True,
            )
            return [
                {**m.metadata, "score": m.score} for m in results.matches if m.metadata
            ]

        except Exception as e:
            logger.error(f"[context] search failed: {e}")
            return []

    async def upsert_memory(
        self,
        *,
        user_id: str,
        kind: str,
        source: str,
        text: str,
        stable_key: Optional[str] = None,
    ) -> bool:
        """Write or overwrite one lean learner-memory record.

        The v1 contract intentionally stays small:
        memory_id, user_id, kind, source, created_at, updated_at, text
        """
        try:
            index = self._get_index()
            ts = datetime.now(timezone.utc).isoformat()
            normalized_kind = (kind or "general").strip().lower().replace(" ", "_")
            normalized_source = (source or "memory").strip() or "memory"
            memory_id = stable_key or f"{user_id}:{normalized_kind}"
            vector = await self.embed(text)

            index.upsert(
                vectors=[
                    {
                        "id": f"context:{memory_id}",
                        "values": vector,
                        "metadata": {
                            "memory_id": memory_id,
                            "user_id": user_id,
                            "kind": normalized_kind,
                            "source": normalized_source,
                            "created_at": ts,
                            "updated_at": ts,
                            "text": text,
                        },
                    }
                ],
                namespace="context",
            )
            logger.debug("[context] upserted learner memory %s", memory_id)
            return True

        except Exception as e:
            logger.error(f"[context] upsert memory failed for {user_id}: {e}")
            return False

    async def upsert_context(
        self,
        *,
        user_id: str,
        text: str,
        metadata: Optional[dict] = None,
    ) -> bool:
        """Backward-compatible wrapper for lean learner-memory writes."""
        metadata = dict(metadata or {})
        kind = str(
            metadata.get("kind")
            or metadata.get("category")
            or metadata.get("source")
            or "general"
        ).strip() or "general"
        source = str(metadata.get("source") or "memory_synthesis").strip() or "memory_synthesis"
        return await self.upsert_memory(
            user_id=user_id,
            kind=kind,
            source=source,
            text=text,
            stable_key=f"{user_id}:{kind}",
        )

    async def delete_memory(self, *, memory_id: str) -> bool:
        """Delete one learner-memory record by memory_id."""

        try:
            index = self._get_index()
            index.delete(ids=[f"context:{memory_id}"], namespace="context")
            logger.debug("[context] deleted learner memory %s", memory_id)
            return True
        except Exception as e:
            logger.error(f"[context] delete memory failed for {memory_id}: {e}")
            return False

    # ── episodic namespace ────────────────────────────────────────────────────
    # Episodic memory is the append-only event stream. Best for
    # recent-study-history retrieval and timeline-style queries.

    async def log_event(
        self, user_id: str, event_type: str, text: str, metadata: dict
    ) -> bool:
        """Append a timestamped event to episodic memory.

        Each call creates a new vector entry (never overwrites).
        event_type must be one of EPISODIC_EVENT_TYPES.
        """
        try:
            if event_type not in EPISODIC_EVENT_TYPES:
                logger.warning(f"[episodic] unknown event_type: {event_type}")

            index = self._get_index()
            vector = await self.embed(text)
            vector_id = f"episodic:{user_id}:{event_type}:{uuid.uuid4().hex[:8]}"
            ts = datetime.now(timezone.utc).isoformat()

            index.upsert(
                vectors=[
                    {
                        "id": vector_id,
                        "values": vector,
                        "metadata": {
                            "user_id": user_id,
                            "event_type": event_type,
                            "text": text,
                            "timestamp": int(datetime.now(timezone.utc).timestamp()),
                            **metadata,
                        },
                    }
                ],
                namespace="episodic",
            )
            logger.debug(f"[episodic] logged {event_type} for {user_id}")
            return True

        except Exception as e:
            logger.error(f"[episodic] log_event failed: {e}")
            return False

    async def upsert_syllabus(
        self, topic_key: str, content: str, metadata: dict
    ) -> bool:
        """Write/overwrite a syllabus entry. Global, no user_id."""
        try:
            index = self._get_index()
            vector = await self.embed(content)
            vector_id = f"syllabus:cbse10:{hashlib.md5(topic_key.encode()).hexdigest()}"
            index.upsert(
                vectors=[
                    {
                        "id": vector_id,
                        "values": vector,
                        "metadata": {
                            "topic_key": topic_key,
                            "content": content,
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                            **metadata,
                        },
                    }
                ],
                namespace="syllabus",
            )
            logger.debug(f"[syllabus] upserted {topic_key}")
            return True
        except Exception as e:
            logger.error(f"[syllabus] upsert failed: {e}")
            return False

    async def search_syllabus(self, query: str, top_k: int = 5) -> list[dict]:
        """Semantic search over CBSE syllabus. No user_id filter."""
        cache_key = ("syllabus", query, top_k)
        if cache_key in self._search_cache:
            return self._search_cache[cache_key]

        last_error = None
        for attempt in range(2):
            try:
                vector = await asyncio.wait_for(self.embed(query), timeout=10)
                results = await asyncio.wait_for(
                    self._query_index(
                        vector=vector,
                        top_k=top_k,
                        namespace="syllabus",
                        include_metadata=True,
                    ),
                    timeout=10,
                )
                items = [
                    {**m.metadata, "score": m.score}
                    for m in results.matches
                    if m.metadata
                ]
                self._search_cache[cache_key] = items
                return items
            except Exception as e:
                last_error = e
                logger.warning(
                    "[syllabus] search attempt %s failed for %r: %s",
                    attempt + 1,
                    query,
                    e,
                )
                await asyncio.sleep(0.25)

        logger.error(f"[syllabus] search failed: {last_error}")
        return []

    async def get_subject_summary(self, subject: str) -> dict:
        """Get summary entry for a subject."""
        try:
            results = await self.search_syllabus(f"{subject} summary", top_k=5)
            for r in results:
                if r.get("type") == "subject_summary" and r.get("subject") == subject:
                    return r
            return {}
        except Exception as e:
            logger.error(f"[syllabus] get_subject_summary failed: {e}")
            return {}

    async def syllabus_is_seeded(self) -> bool:
        """Check if syllabus namespace has data."""
        try:
            results = await self.search_syllabus("CBSE Mathematics", top_k=1)
            return len(results) > 0
        except Exception:
            return False

    def format_syllabus_for_prompt(self, results: list[dict]) -> str:
        """Format syllabus results for injection into agent context."""
        if not results:
            return ""

        year = results[0].get("academic_year", "2025-26")
        lines = [f"[CBSE CLASS 10 SYLLABUS {year}]"]
        seen = set()

        for r in results:
            subject = r.get("subject", "")
            chapter = r.get("chapter_name", "")
            if not chapter or f"{subject}|{chapter}" in seen:
                continue
            seen.add(f"{subject}|{chapter}")

            is_deleted = r.get("is_deleted", False)
            weightage = r.get("weightage_marks", 0)
            topics = []
            try:
                topics = json.loads(r.get("topics_json", "[]"))
            except Exception:
                pass

            status = "DELETED" if is_deleted else "active"
            weight_str = f" ({weightage}m)" if weightage else ""
            topic_str = f" | {', '.join(topics[:4])}" if topics else ""

            lines.append(f"{subject} - {chapter} [{status}]{weight_str}{topic_str}")

        return "\n".join(lines)

    async def search_episodic(
        self,
        user_id: str,
        query: str,
        top_k: int = 10,
        event_type: Optional[str] = None,
        days: int = 30,
    ) -> list[dict]:
        """Semantic search over episodic events. Optionally filter by event_type and time."""
        try:
            from datetime import datetime, timedelta, timezone

            index = self._get_index()
            vector = await self.embed(query)

            filter_dict = {"user_id": {"$eq": user_id}}

            # Time filter: only last X days (use Unix timestamp as number)
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            cutoff_unix = int(cutoff.timestamp())
            filter_dict["timestamp"] = {"$gte": cutoff_unix}

            if event_type:
                filter_dict["event_type"] = {"$eq": event_type}

            results = index.query(
                vector=vector,
                top_k=top_k,
                namespace="episodic",
                filter=filter_dict,
                include_metadata=True,
            )
            return [
                {**m.metadata, "score": m.score} for m in results.matches if m.metadata
            ]

        except Exception as e:
            logger.error(f"[episodic] search failed: {e}")
            return []

    async def get_recent_episodic(
        self, user_id: str, top_k: int = 20, days: int = 30
    ) -> list[dict]:
        """Fetch recent events sorted by timestamp descending. Default: last 30 days."""
        try:
            from datetime import datetime, timedelta, timezone

            index = self._get_index()
            dummy_vector = [0.0] * EMBEDDING_DIM

            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            cutoff_unix = int(cutoff.timestamp())

            results = index.query(
                vector=dummy_vector,
                top_k=top_k,
                namespace="episodic",
                filter={
                    "user_id": {"$eq": user_id},
                    "timestamp": {"$gte": cutoff_unix},
                },
                include_metadata=True,
            )
            items = [m.metadata for m in results.matches if m.metadata]
            items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            return items

        except Exception as e:
            logger.error(f"[episodic] get_recent failed: {e}")
            return []

    # ── backlog namespace ─────────────────────────────────────────────────────
    # Backlog stores unfinished topics in an LLM-friendly form. One entry
    # per topic per user, rewritten on each update (never appended).
    # Enables intake to quickly surface pending work without heavy graph queries.

    def _build_backlog_text(self, match_key: str, data: dict) -> str:
        """Build a human-readable text summary of a topic's progress.

        This text is what gets embedded for semantic search. It should
        be concise but contain enough signal for retrieval.
        """
        status = data.get("status", "PENDING")
        diff = data.get("difficulty_signal") or "unknown"
        hours_act = data.get("hours_actual", 0)
        subs_done = data.get("subtopics_completed", [])
        subs_pending = data.get("subtopics_pending") or data.get(
            "subtopics_remaining", []
        )
        last = data.get("last_studied", "never")
        mode = data.get("study_mode", "normal")
        mastery = data.get("mastery_level", "NOT_STARTED")

        hours_est = data.get("hours_estimated", 0)

        lines = [
            f"{match_key} — {status}, difficulty: {diff}.",
            f"({hours_est}h total, {hours_act}h done).",
        ]
        if subs_pending:
            lines.append(f"Subtopics pending: {', '.join(subs_pending)}.")
        if subs_done:
            lines.append(f"Subtopics completed: {', '.join(subs_done)}.")
        lines.append(f"Last studied: {last}. study_mode: {mode}. mastery: {mastery}.")
        return " ".join(lines)

    async def upsert_backlog(self, user_id: str, match_key: str, data: dict) -> bool:
        """Write or overwrite one backlog entry for a topic.

        One topic/match_key maps to one vector ID per user. This is a
        rewritten summary of progress, not an event log. List fields
        are JSON-serialized because Pinecone metadata is flat.
        """
        try:
            index = self._get_index()
            text = self._build_backlog_text(match_key, data)
            vector = await self.embed(text)
            vector_id = self._backlog_vector_id(user_id, match_key)
            ts = datetime.now(timezone.utc).isoformat()
            pending = data.get("subtopics_pending") or data.get(
                "subtopics_remaining", []
            )

            index.upsert(
                vectors=[
                    {
                        "id": vector_id,
                        "values": vector,
                        "metadata": {
                            "user_id": user_id,
                            "match_key": match_key,
                            "text": text,
                            "status": data.get("status", "PENDING"),
                            "difficulty_signal": data.get("difficulty_signal") or "",
                            "study_mode": data.get("study_mode", "normal"),
                            "mastery_level": data.get("mastery_level", "NOT_STARTED"),
                            "hours_actual": float(data.get("hours_actual", 0)),
                            "hours_estimated": float(data.get("hours_estimated", 0)),
                            "subtopics_json": json.dumps(data.get("subtopics", [])),
                            "subtopics_completed_json": json.dumps(
                                data.get("subtopics_completed", [])
                            ),
                            "subtopics_pending_json": json.dumps(pending),
                            "content_match_keys_json": json.dumps(
                                data.get("content_match_keys", [])
                            ),
                            "last_studied": data.get("last_studied") or "",
                            "updated_at": ts,
                        },
                    }
                ],
                namespace=BACKLOG_NAMESPACE,
            )
            logger.debug(f"[backlog] upserted {vector_id}")
            return True

        except Exception as e:
            logger.error(f"[backlog] upsert failed for {match_key}: {e}")
            return False

    async def upsert(
        self,
        namespace: str,
        key: str,
        data: dict,
    ) -> bool:
        """Generic upsert for any namespace."""
        try:
            index = self._get_index()
            ts = datetime.now(timezone.utc).isoformat()

            # Build text for embedding
            text = json.dumps(data)

            # Get embedding
            vector = await self.embed(text)

            vector_id = self._vector_id(namespace, key, data)
            index.upsert(
                vectors=[
                    {
                        "id": vector_id,
                        "values": vector,
                        "metadata": {
                            **data,
                            "updated_at": ts,
                        },
                    }
                ],
                namespace=namespace,
            )
            return True
        except Exception as e:
            logger.error(f"[{namespace}] upsert failed for {key}: {e}")
            return False

    async def search_backlog(
        self, user_id: str, query: str, top_k: int = 10
    ) -> list[dict]:
        """Semantic search over a user's backlog topics.

        Used by intake to find existing topics before creating new ones.
        Results are cached and filtered by a minimum similarity score.
        """
        cache_key = ("backlog", user_id, query, top_k)
        if cache_key in self._search_cache:
            return self._search_cache[cache_key]

        last_error = None
        for attempt in range(2):
            try:
                vector = await asyncio.wait_for(self.embed(query), timeout=10)
                results = await asyncio.wait_for(
                    self._query_index(
                        vector=vector,
                        top_k=top_k,
                        namespace=BACKLOG_NAMESPACE,
                        filter={"user_id": {"$eq": user_id}},
                        include_metadata=True,
                    ),
                    timeout=10,
                )

                items = []
                for m in results.matches:
                    if m.score < 0.55:
                        continue
                    if not m.metadata:
                        continue
                    item = self._normalize_backlog_metadata(m.metadata)
                    item["score"] = m.score
                    items.append(item)

                self._search_cache[cache_key] = items
                return items

            except Exception as e:
                last_error = e
                logger.warning(
                    "[backlog] search attempt %s failed for user=%r query=%r: %s",
                    attempt + 1,
                    user_id,
                    query,
                    e,
                )
                await asyncio.sleep(0.25)

        logger.error(f"[backlog] search failed: {last_error}")
        return []

    async def get_all_backlog(self, user_id: str) -> list[dict]:
        """Fetch ALL backlog entries for a user (used by intake at session start)."""
        try:
            index = self._get_index()
            dummy_vector = [0.0] * EMBEDDING_DIM

            results = index.query(
                vector=dummy_vector,
                top_k=50,
                namespace=BACKLOG_NAMESPACE,
                filter={"user_id": {"$eq": user_id}},
                include_metadata=True,
            )

            items = []
            for m in results.matches:
                if not m.metadata:
                    continue
                items.append(self._normalize_backlog_metadata(m.metadata))

            return items

        except Exception as e:
            logger.error(f"[backlog] get_all failed: {e}")
            return []

    # ── combined memory ───────────────────────────────────────────────────────
    # These helpers bridge raw vector namespaces into prompt-ready bundles.
    # Agents call load_full_memory() to get everything they need in one shot.

    async def load_full_memory(
        self, user_id: str, query: str = "", days: int = 30
    ) -> dict:
        """Load the full memory bundle for an agent turn.

        Returns context (learner memory), recent_activity (what happened),
        and optionally relevant_episodic (semantic search over events).
        """
        context = await self.get_all_context(user_id)
        recent = await self.get_recent_episodic(user_id, top_k=20, days=days)

        result = {
            "context": context,
            "recent_activity": recent,
            "relevant_episodic": [],
        }

        if query:
            result["relevant_episodic"] = await self.search_episodic(
                user_id, query, top_k=5, days=days
            )

        return result

    def format_memory_for_prompt(self, memory: dict) -> str:
        """Format combined memory into a prompt-friendly text block.

        This is intentionally lossy and human-readable. It exists for model
        context injection, not for reconstructing canonical state.
        """
        lines = []

        if memory.get("context"):
            lines.append("=== LEARNER MEMORY ===")
            context_items = sorted(
                memory["context"],
                key=lambda item: (
                    str(item.get("kind") or item.get("category") or "zzz"),
                    str(item.get("updated_at") or ""),
                ),
            )
            for item in context_items:
                kind = str(item.get("kind") or item.get("category") or "memory").replace("_", " ").strip()
                text = str(item.get("text", "") or "").strip()
                if not text:
                    continue
                lines.append(f"- [{kind}] {text}")

        if memory.get("recent_activity"):
            lines.append("\n=== RECENT ACTIVITY (last 20 events) ===")
            for item in memory["recent_activity"][:10]:
                timestamp = item.get("timestamp")
                if isinstance(timestamp, (int, float)):
                    ts = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")
                else:
                    ts = str(timestamp or "")[:10]
                event_type = str(item.get("event_type") or "event").replace("_", " ")
                text = str(item.get("text", "") or "").strip()
                if not text:
                    continue
                lines.append(f"- [{ts}] ({event_type}) {text}")

        return "\n".join(lines)

    # ── convenience wrappers ──────────────────────────────────────────────────

    async def log_plan_created(
        self,
        user_id: str,
        plan_id: str,
        topics: list[str],
        total_hours: float,
        intensity: str,
    ) -> bool:
        """Log when a new plan is committed."""
        text = (
            f"New plan created: {plan_id}. "
            f"Topics: {', '.join(topics)}. "
            f"Total: {total_hours}h. Intensity: {intensity}."
        )
        return await self.log_event(
            user_id=user_id,
            event_type="plan_created",
            text=text,
            metadata={
                "plan_id": plan_id,
                "topics": json.dumps(topics),
                "total_hours": total_hours,
                "intensity": intensity,
            },
        )
