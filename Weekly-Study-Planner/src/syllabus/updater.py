"""
CBSE Syllabus Updater
======================
Seeds Pinecone on first startup.
Runs monthly via APScheduler.
Fetches from Tavily — no hardcoded sites.
LLM extracts structured data.

Run manually:
  python -m src.syllabus.updater
  python -m src.syllabus.updater --subject Science
  python -m src.syllabus.updater --check
"""

import os
import json
import asyncio
import logging
import argparse
import requests
from datetime import datetime, timezone
from typing import Optional, List
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()
logger = logging.getLogger(__name__)

ACADEMIC_YEAR = "2025-26"

SUBJECTS = [
    "Mathematics",
    "Science",
    "English",
    "Social Science",
    "Hindi",
    "Sanskrit",
]


class ChapterEntry(BaseModel):
    """New unified chapter entry structure."""

    # Identifiers
    chapter_name: str
    chapter_number: Optional[int] = None

    # Weightage
    weightage_marks: Optional[int] = None
    is_deleted: bool = False
    key_topics: List[str] = Field(default_factory=list)
    deleted_topics: List[str] = Field(default_factory=list)

    # New fields (used for storage)
    subject_total_marks: Optional[int] = None
    chapter_weightage_marks: Optional[int] = None
    active_topics: List[str] = Field(default_factory=list)
    removed_topics: List[str] = Field(default_factory=list)
    chapter_status: str = "active"
    status: str = "monthly_search"
    last_updated: str = ""


class SubjectExtraction(BaseModel):
    """Subject-level extraction with chapter entries."""

    subject: str
    chapters: List[ChapterEntry] = Field(default_factory=list)
    deleted_chapters: List[str] = Field(default_factory=list)
    subject_total_marks: Optional[int] = None
    total_theory_marks: Optional[int] = None
    total_internal_marks: Optional[int] = None


class TopicExtraction(BaseModel):
    """Legacy - keeping for backward compatibility."""

    chapter_name: str
    topics: List[str] = Field(default_factory=list)
    deleted_topics: List[str] = Field(default_factory=list)
    board_important: List[str] = Field(default_factory=list)


def _tavily(query: str, depth: str = "basic", max_results: int = 4) -> str:
    """Search Tavily. Returns combined content string."""
    try:
        key = os.getenv("TAVILY_API_KEY")
        if not key:
            return ""
        res = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": key,
                "query": query,
                "search_depth": depth,
                "max_results": max_results,
            },
            timeout=12,
        )
        if res.status_code == 200:
            results = res.json().get("results", [])
            return "\n".join(
                [f"[{r.get('url', '')}]\n{r.get('content', '')[:800]}" for r in results]
            )
        return ""
    except Exception as e:
        logger.error(f"Tavily failed: {e}")
        return ""


async def _extract_subject(subject: str, raw: str) -> SubjectExtraction:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage

    try:
        llm = ChatOpenAI(
            model="gpt-4.1-mini",
            temperature=0.4,
            api_key=os.getenv("OPENAI_API_KEY"),
        ).with_structured_output(SubjectExtraction)

        result = await llm.ainvoke(
            [
                SystemMessage(
                    content=f"""Extract CBSE Class 10 syllabus ONLY for {subject} for academic year {ACADEMIC_YEAR}.

CRITICAL: This is Class 10 (NOT Class 9, NOT Class 11/12). Extract ONLY Class 10 chapters.

CBSE Class 10 {subject} has UNITS, and each unit has multiple CHAPTERS inside it.
Extract individual CHAPTERS (not units).
The weightage is at unit level — distribute it proportionally across chapters within that unit.


Example:
Unit A (25 marks) contains:
- Chapter 1: X
- Chapter 2: Y
- Chapter 3: Z

Do this for ALL units.

"""

                ),
                HumanMessage(content=f"Extract Class 10 {subject} syllabus:\n\n{raw}"),
            ]
        )
        result.subject = subject
        return result
    except Exception as e:
        logger.error("Extraction failed {subject}: {e}")
        return SubjectExtraction(subject=subject)


async def _extract_topics(subject: str, chapter: str, raw: str) -> TopicExtraction:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage

    try:
        llm = ChatOpenAI(
            model="openai/gpt-4o-mini",
            temperature=0,
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
        ).with_structured_output(TopicExtraction)

        result = await llm.ainvoke(
            [
                SystemMessage(
                    content=f"""Extract detailed topics for CBSE Class 10 {subject} - {chapter} ({ACADEMIC_YEAR}).
Extract all topics, deleted topics, and board-important topics."""
                ),
                HumanMessage(content=f"Extract topics:\n\n{raw[:5000]}"),
            ]
        )
        return result
    except Exception as e:
        logger.error(f"Topic extraction failed {chapter}: {e}")
        return TopicExtraction(chapter_name=chapter)


async def _store_subject(extraction: SubjectExtraction, vs):
    ts = datetime.now(timezone.utc).isoformat()
    stored = 0

    for ch in extraction.chapters:
        active_topics = ch.active_topics or ch.key_topics or []
        removed_topics = ch.removed_topics or ch.deleted_topics or []
        chapter_weightage = ch.chapter_weightage_marks or ch.weightage_marks or 0
        chapter_status = (
            ch.chapter_status
            if ch.chapter_status
            else ("deleted" if ch.is_deleted else "active")
        )

        search_text = (
            f"CBSE Class 10 {extraction.subject} Chapter {ch.chapter_number or 0} {ch.chapter_name}. "
            f"Weightage: {chapter_weightage} marks out of {extraction.subject_total_marks or 100}. "
            f"Status: {chapter_status}. "
            f"Active Topics: {', '.join(active_topics) if active_topics else 'none'}. "
            f"Removed Topics: {', '.join(removed_topics) if removed_topics else 'none'}."
        )

        await vs.upsert_syllabus(
            topic_key=f"{extraction.subject}|{ch.chapter_name}",
            content=search_text,
            metadata={
                "topic_key": f"{extraction.subject}|{ch.chapter_name}",
                "subject": extraction.subject,
                "chapter_name": ch.chapter_name,
                "chapter_number": ch.chapter_number or 0,
                "subject_total_marks": extraction.subject_total_marks or 0,
                "chapter_weightage_marks": chapter_weightage,
                "active_topics": json.dumps(active_topics),
                "removed_topics": json.dumps(removed_topics),
                "search_text": search_text,
                "chapter_status": chapter_status,
                "status": "monthly_search",
                "academic_year": ACADEMIC_YEAR,
                "last_updated": ts,
            },
        )
        stored += 1

    logger.info(f"[SYLLABUS] Stored {stored} chapter vectors for {extraction.subject}")
    return stored


async def fetch_chapter_topics(subject: str, chapter: str, vs) -> bool:
    """Lazy topic fetch — called when user first mentions a chapter."""
    logger.info(f"[SYLLABUS] Lazy fetch: {subject} - {chapter}")

    raw = _tavily(
        f"site:cbseacademic.nic.in Class 10 {subject} {chapter} {ACADEMIC_YEAR} "
        f"topics subtopics board exam important"
    )
    if not raw:
        return False

    extraction = await _extract_topics(subject, chapter, raw)
    ts = datetime.now(timezone.utc).isoformat()

    existing = await vs.search_syllabus(f"{subject} {chapter}", top_k=1)
    if existing:
        meta = dict(existing[0])
        meta["topics_json"] = json.dumps(extraction.topics)
        meta["deleted_topics_json"] = json.dumps(extraction.deleted_topics)
        meta["board_important_json"] = json.dumps(extraction.board_important)
        meta["topics_fetched"] = True
        meta["updated_at"] = ts

        content = (
            f"CBSE Class 10 {subject} - {chapter}. "
            f"Topics: {', '.join(extraction.topics)}. "
            f"Board important: {', '.join(extraction.board_important)}."
        )
        await vs.upsert_syllabus(
            topic_key=f"{subject}|{chapter}", content=content, metadata=meta
        )
    return True


async def update_subject(subject: str, vs) -> bool:
    logger.info(f"\n{'=' * 40}\n Updating {subject}\n{'=' * 40}")

    raw = _tavily(
        f"site:cbseacademic.nic.in Class 10 {subject} syllabus {ACADEMIC_YEAR} "
    )
    if not raw:
        logger.warning(f"No results for {subject}")
        return False

    extraction = await _extract_subject(subject, raw)
    if not extraction.chapters:
        logger.warning(f"No chapters extracted for {subject}")
        return False

    await _store_subject(extraction, vs)
    return True


async def run_full_update(subjects: Optional[List[str]] = None):
    from src.database.vector_store import VectorStore

    vs = VectorStore()
    targets = subjects or SUBJECTS
    logger.info(f"[SYLLABUS] Monthly update for {ACADEMIC_YEAR}")

    results = {}
    for subject in targets:
        try:
            ok = await update_subject(subject, vs)
            results[subject] = "ok" if ok else "failed"
        except Exception as e:
            logger.error(f"Failed {subject}: {e}")
            results[subject] = f"error: {e}"
        await asyncio.sleep(2)

    logger.info(f"[SYLLABUS] Done: {results}")
    return results


async def seed_if_empty():
    from src.database.vector_store import VectorStore

    vs = VectorStore()
    seeded = await vs.syllabus_is_seeded()
    if not seeded:
        logger.info("[SYLLABUS] Empty — seeding...")
        await run_full_update()
    else:
        logger.info("[SYLLABUS] Already seeded")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--subject")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.check:

        async def check():
            from src.database.vector_store import VectorStore

            vs = VectorStore()
            for s in SUBJECTS:
                r = await vs.search_syllabus(f"CBSE {s}", top_k=2)
                print("R is", r)

                print(f"{'OK' if r else 'EMPTY'} {s}: {len(r)} entries")

        asyncio.run(check())
    elif args.subject:
        asyncio.run(run_full_update([args.subject]))
    else:
        asyncio.run(run_full_update())
