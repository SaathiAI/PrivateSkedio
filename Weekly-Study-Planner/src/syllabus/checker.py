"""
CBSE Syllabus Contradiction Checker
=====================================
Tool used by all 3 agents (intake, planner, reschedule).

What it does:
- Checks if chapter is active/deleted in 2025-26
- Lazy fetches topics on first mention (background)
- Self-heals when user contradicts stored data
- Refreshes stale entries in background
"""

import os
import json
import asyncio
import logging
import requests
from datetime import datetime, timezone, timedelta
from langchain_core.tools import tool

logger = logging.getLogger(__name__)
ACADEMIC_YEAR = "2025-26"


def _is_stale(updated_at: str, days: int = 30) -> bool:
    try:
        dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days > days
    except Exception:
        return True


def _tavily_quick(query: str) -> str:
    try:
        key = os.getenv("TAVILY_API_KEY")
        res = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": key,
                "query": query,
                "search_depth": "basic",
                "max_results": 3,
            },
            timeout=10,
        )
        if res.status_code == 200:
            return " ".join(
                [r.get("content", "")[:500] for r in res.json().get("results", [])]
            )
        return ""
    except Exception as e:
        logger.error(f"Tavily quick failed: {e}")
        return ""


@tool
async def check_chapter_in_syllabus(subject: str, chapter_name: str) -> dict:
    """
    Check if a CBSE Class 10 chapter is in the 2025-26 syllabus.

    Call this when:
    - User mentions any chapter to study
    - You want topics inside a chapter for subtopic suggestions
    - User says their teacher told them something changed

    Args:
        subject: e.g. "Mathematics", "Science", "English", "Social Science"
        chapter_name: e.g. "Polynomials", "Life Processes", "Chemical Reactions"

    Returns dict with:
        status: "active" / "deleted" / "unknown"
        topics: list of topics in this chapter
        weightage_marks: marks weightage
        is_stale: data might be outdated (refresh happening in background)
    """
    from src.database.vector_store import VectorStore
    from src.syllabus.updater import fetch_chapter_topics

    vs = VectorStore()
    results = await vs.search_syllabus(f"{subject} {chapter_name}", top_k=3)

    if not results:
        # Not in DB → Tavily search → store → return
        logger.info(f"[CHECKER] {chapter_name} not in DB, fresh search...")
        raw = _tavily_quick(
            f"CBSE Class 10 {subject} {chapter_name} "
            f"{ACADEMIC_YEAR} syllabus active deleted removed"
        )

        if raw:
            deleted_words = [
                "deleted",
                "removed",
                "not in syllabus",
                "excluded",
                "dropped",
                "not included",
                "no longer",
            ]
            is_deleted = any(w in raw.lower() for w in deleted_words)

            await vs.upsert_syllabus(
                topic_key=f"{subject}|{chapter_name}",
                content=f"CBSE Class 10 {subject} - {chapter_name}: {raw[:800]}",
                metadata={
                    "subject": subject,
                    "chapter_name": chapter_name,
                    "is_deleted": is_deleted,
                    "topics_json": "[]",
                    "topics_fetched": False,
                    "academic_year": ACADEMIC_YEAR,
                    "source": "tavily_on_demand",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            return {
                "found": True,
                "status": "deleted" if is_deleted else "active",
                "chapter_name": chapter_name,
                "subject": subject,
                "topics": [],
                "weightage_marks": 0,
                "source": "fresh_search",
                "note": "Freshly fetched and stored",
            }

        return {
            "found": False,
            "status": "unknown",
            "chapter_name": chapter_name,
            "subject": subject,
            "note": "Not found. Proceed with caution.",
        }

    # Found in DB
    best = results[0]
    is_deleted = best.get("is_deleted", False)
    updated_at = best.get("updated_at", "")
    stale = _is_stale(updated_at, days=30)
    topics_fetched = best.get("topics_fetched", False)

    topics = []
    try:
        topics = json.loads(best.get("topics_json", "[]"))
    except Exception:
        pass

    deleted_topics = []
    try:
        deleted_topics = json.loads(best.get("deleted_topics_json", "[]"))
    except Exception:
        pass

    board_important = []
    try:
        board_important = json.loads(best.get("board_important_json", "[]"))
    except Exception:
        pass

    # Lazy fetch topics in background if not yet done
    if not topics_fetched and not is_deleted:
        asyncio.create_task(fetch_chapter_topics(subject, chapter_name, vs))

    # Stale → refresh in background
    if stale:

        async def _bg_refresh():
            raw = _tavily_quick(
                f"CBSE Class 10 {subject} {chapter_name} "
                f"{ACADEMIC_YEAR} syllabus topics"
            )
            if raw:
                await fetch_chapter_topics(subject, chapter_name, vs)

        asyncio.create_task(_bg_refresh())

    return {
        "found": True,
        "status": "deleted" if is_deleted else "active",
        "chapter_name": best.get("chapter_name", chapter_name),
        "subject": subject,
        "topics": topics,
        "deleted_topics": deleted_topics,
        "board_important": board_important,
        "weightage_marks": best.get("weightage_marks", 0),
        "academic_year": ACADEMIC_YEAR,
        "last_updated": updated_at[:10] if updated_at else "unknown",
        "is_stale": stale,
        "topics_fetched": topics_fetched,
    }
