"""Runtime learner-memory loading and prompt-context shaping for SkedioAI."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _with_default_profile_fields(
    neo4j_user: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Backfill missing learner profile fields with product defaults."""

    if not neo4j_user:
        return neo4j_user

    normalized = dict(neo4j_user)
    if not normalized.get("grade"):
        normalized["grade"] = "10"
    if not normalized.get("board"):
        normalized["board"] = "CBSE"
    return normalized


def _structured_user_facts(neo4j_user: Optional[Dict[str, Any]]) -> list[str]:
    """Render stable structured profile facts from Neo4j as brief bullets."""

    if not neo4j_user:
        return []

    fields = []
    name = neo4j_user.get("name")
    grade = neo4j_user.get("grade")
    board = neo4j_user.get("board")
    if name:
        fields.append(f"- name: {name}")
    if grade:
        fields.append(f"- grade: {grade}")
    if board:
        fields.append(f"- board: {board}")

    return fields


def _memory_sort_key(item: Dict[str, Any]) -> tuple[str, str]:
    return (
        str(item.get("kind") or item.get("category") or "memory"),
        str(item.get("updated_at") or item.get("created_at") or ""),
    )


def _format_learner_records(records: list[Dict[str, Any]], limit: int = 8) -> list[str]:
    """Render lean learner-memory records without leaking raw storage shape."""

    lines = []
    seen = set()
    for item in sorted(records or [], key=_memory_sort_key):
        text = str(item.get("text") or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        kind = str(item.get("kind") or item.get("category") or "memory")
        kind = kind.replace("_", " ").strip()
        lines.append(f"- [{kind}] {text}")
        if len(lines) >= limit:
            break
    return lines


def _format_event_date(item: Dict[str, Any]) -> str:
    timestamp = item.get("timestamp")
    if isinstance(timestamp, (int, float)):
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")
    raw = str(item.get("updated_at") or item.get("created_at") or "")[:10]
    return raw or "recent"


def _format_recent_activity(records: list[Dict[str, Any]], limit: int = 5) -> list[str]:
    """Render recent events as context, not as long-term learner truth."""

    lines = []
    seen = set()
    for item in records or []:
        text = str(item.get("text") or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        event_type = str(item.get("event_type") or item.get("kind") or "event")
        event_type = event_type.replace("_", " ").strip()
        lines.append(f"- [{_format_event_date(item)}] ({event_type}) {text}")
        if len(lines) >= limit:
            break
    return lines


async def build_learner_memory_brief(
    *,
    user_id: str,
    query: str = "",
    days: int = 30,
    neo4j: Any = None,
    vector_store: Any = None,
) -> str:
    """Return the short learner-memory brief injected into live agent runs."""

    if neo4j is None:
        from src.database.neo4j import Neo4jManager

        neo4j = Neo4jManager()
    if vector_store is None:
        from src.database.vector_store import VectorStore

        vector_store = VectorStore()

    try:
        neo4j_user = neo4j.get_user_model(user_id)
    except Exception:
        neo4j_user = None
    neo4j_user = _with_default_profile_fields(neo4j_user)

    try:
        memory = await vector_store.load_full_memory(user_id, query=query, days=days)
    except Exception:
        memory = {"context": [], "recent_activity": [], "relevant_episodic": []}

    sections = ["=== LEARNER MEMORY BRIEF ==="]

    fact_lines = _structured_user_facts(neo4j_user)
    if fact_lines:
        sections.append("Learner facts:")
        sections.extend(fact_lines)

    learner_lines = _format_learner_records(memory.get("context", []))
    if learner_lines:
        if len(sections) > 1:
            sections.append("")
        sections.append("Remembered learner patterns:")
        sections.extend(learner_lines)

    relevant = memory.get("relevant_episodic") or []
    recent = memory.get("recent_activity") or []
    activity_lines = _format_recent_activity(relevant or recent)
    if activity_lines:
        if len(sections) > 1:
            sections.append("")
        sections.append("Recent relevant activity:")
        sections.extend(activity_lines)

    if len(sections) == 1:
        sections.append("- No prior learner memory available.")

    sections.append("")
    sections.append(
        "Use this as planning guidance, not as a hard rule or source of exact plan truth."
    )
    return "\n".join(sections).strip()


async def build_runtime_user_context(
    *,
    user_id: str,
    query: str = "",
    days: int = 30,
) -> str:
    """Compatibility wrapper for routes that still pass `user_context`."""

    return await build_learner_memory_brief(user_id=user_id, query=query, days=days)
