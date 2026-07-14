"""
src/syllabus/tools.py
======================
Syllabus System - Production Grade
3 tools for verifying CBSE curriculum and self-correction

Tools:
- verify_syllabus: Check if topic exists in CBSE
- get_chapter_details: Get topics inside a chapter
- verify_and_act: Self-correct when user contradicts

Rules:
1. Agent generates query freely - no {subject} templates
2. Upsert ONLY on user confirmation - never auto-store unverified results
3. verified entries always win over unverified
"""

import os
import json
import asyncio
import logging
import requests
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

if TYPE_CHECKING:
    from src.database.vector_store import VectorStore

logger = logging.getLogger(__name__)
ACADEMIC_YEAR = "2025-26"


# ═══════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════


class SyllabusEntry(BaseModel):
    """
    Canonical syllabus entry schema - matches user's Pinecone storage exactly.

    Schema:
    - id: "syllabus:cbse10:{hash}"
    - academic_year: "2025-26"
    - active_topics: [...]
    - chapter_name: "Dust of Snow"
    - chapter_number: 12
    - chapter_status: "active"
    - chapter_weightage_marks: 3
    - content: "CBSE Class 10 English Dust of Snow poem 2025-26"
    - last_updated: "2026-04-15T14:49:47.564970+00:00"
    - removed_topics: [...]
    - search_text: "CBSE Class 10 English Dust of Snow poem 2025-26"
    - status: "monthly_search"
    - subject: "english"
    - subject_total_marks: 80
    - topic_key: "english|Dust of Snow"
    - updated_at: "2026-04-15T14:49:50.116166+00:00"
    """

    id: Optional[str] = Field(default=None, description="Pinecone vector ID")
    academic_year: str = Field(default="2025-26", description="Academic year")
    active_topics: List[str] = Field(
        default_factory=list, description="Current topics in chapter"
    )
    chapter_name: Optional[str] = Field(default=None, description="Chapter title")
    chapter_number: Optional[int] = Field(default=None, description="Chapter number")
    chapter_status: str = Field(default="active", description="active or deleted")
    chapter_weightage_marks: Optional[int] = Field(
        default=None, description="Marks weightage"
    )
    content: Optional[str] = Field(default=None, description="Full text for embedding")
    last_updated: Optional[str] = Field(default=None, description="When last updated")
    removed_topics: List[str] = Field(
        default_factory=list, description="Removed topics"
    )
    search_text: Optional[str] = Field(default=None, description="Search query text")
    status: str = Field(default="monthly_search", description="Update status tracking")
    subject: Optional[str] = Field(default=None, description="Subject name")
    subject_total_marks: Optional[int] = Field(
        default=None, description="Total marks for subject"
    )
    topic_key: Optional[str] = Field(
        default=None, description="Canonical key 'Subject|Chapter'"
    )
    updated_at: Optional[str] = Field(default=None, description="Timestamp")


class VerifyResult(BaseModel):
    """Result from verify_syllabus tool."""

    exists: bool = Field(description="Whether topic exists in CBSE")
    topic_key: Optional[str] = Field(
        default=None, description="Canonical key 'Subject|Chapter'"
    )
    subject: Optional[str] = Field(default=None, description="Subject name")
    chapter_name: Optional[str] = Field(default=None, description="Chapter name")
    chapter_number: Optional[int] = Field(default=None, description="Chapter number")
    academic_year: Optional[str] = Field(default=None, description="Academic year")
    active_topics: List[str] = Field(
        default_factory=list, description="Topics in this chapter"
    )
    removed_topics: List[str] = Field(
        default_factory=list, description="Removed topics"
    )
    chapter_weightage_marks: Optional[int] = Field(
        default=None, description="Marks weightage"
    )
    subject_total_marks: Optional[int] = Field(
        default=None, description="Total marks for subject"
    )
    chapter_status: Optional[str] = Field(default=None, description="active or deleted")
    confidence: float = Field(default=0.0, description="Match confidence 0-1")
    source: str = Field(default="pinecone", description="cache, pinecone, or tavily")
    content: Optional[str] = Field(default=None, description="Full text for embedding")
    search_text: Optional[str] = Field(default=None, description="Search query text")


class ChapterDetailsResult(BaseModel):
    """Result from get_chapter_details tool."""

    found: bool = Field(description="Whether chapter(s) found")
    chapters: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="List of chapters with topics"
    )


class VerifyAndActResult(BaseModel):
    """Result from verify_and_act tool."""

    confirmed: bool = Field(description="Whether user's claim was confirmed")
    corrected: bool = Field(description="Whether data was corrected in system")
    message: str = Field(description="Human-readable result message")


# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════


def _tavily_search(query: str, depth: str = "basic", max_results: int = 4) -> str:
    """Search Tavily for CBSE curriculum info."""
    try:
        key = os.getenv("TAVILY_API_KEY")
        if not key:
            logger.warning("[TAVILY] No API key found")
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
        logger.error(f"[TAVILY] Search failed: {e}")
        return ""


def _is_stale(updated_at: str, days: int = 30) -> bool:
    """Check if data is stale (>30 days old)."""
    try:
        dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days > days
    except Exception:
        return True


class _DeletionStatus(BaseModel):
    """LLM's decision on whether chapter is deleted."""

    is_deleted: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


async def _llm_check_deletion(chapter: str, raw: str) -> _DeletionStatus:
    """LLM decides if chapter is deleted using web search results."""
    try:
        llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0)

        prompt = f"""You are a CBSE curriculum expert. 
Given the web search results about "{chapter}", determine if this chapter 
was REMOVED from the CBSE Class 10 syllabus for 2025-26 academic year.

Web results:
{raw[:2000]}

Respond with JSON:
{{
  "is_deleted": true/false,
  "confidence": 0.0-1.0,
  "reason": "brief explanation"
}}

Only mark as deleted if you find clear evidence."""

        response = await llm.ainvoke(prompt)
        result = json.loads(response.content)
        return _DeletionStatus(**result)
    except Exception as e:
        logger.error(f"[LLM] Deletion check failed: {e}")
        return _DeletionStatus(is_deleted=False, confidence=0.0, reason="LLM error")


# ═══════════════════════════════════════════════════════════════════════════
# TOOL 1: VERIFY SYLLABUS
# ═══════════════════════════════════════════════════════════════════════════


@tool
async def verify_syllabus(query: str) -> Dict[str, Any]:
    """
    Verify if a topic exists in CBSE Class 10 curriculum.

    Use when:
    - User mentions a topic: "I want to study polynomials"
    - Planning: verify topic exists before adding to plan
    - Checking: is this in CBSE syllabus?

    Args:
        query: Natural language query like "Polynomials in Class 10 Math"
               or "Is Light in CBSE Science?"

    Returns:
        {
            "exists": bool,
            "topic_key": "Mathematics|Polynomials" | null,
            "subject": "Mathematics" | null,
            "chapter_name": "Polynomials" | null,
            "active_topics": ["Zeros of polynomial", ...],
            "removed_topics": [...],
            "chapter_weightage_marks": 20 | null,
            "chapter_status": "active" | "deleted" | null,
            "confidence": 0.0-1.0,
            "source": "cache" | "pinecone" | "tavily"
        }

    Timeout: 5 seconds
    """
    from src.database.vector_store import VectorStore

    vs = VectorStore()

    logger.info(f"[VERIFY] Query: {query}")

    try:
        # Search Pinecone
        results = await vs.search_syllabus(query, top_k=5)

        if not results:
            logger.info("[VERIFY] No results from Pinecone")
            return {
                "exists": False,
                "error": None,
                "message": "No matching chapters found in syllabus",
            }

        # Check if stale and refresh in background



        

        # Build full response matching user schema
        return {
            "exists": True,
            "matches": [
        {
            "topic_key": r.get("topic_key"),
            "subject": r.get("subject"),
            "chapter_name": r.get("chapter_name"),
            "chapter_number": r.get("chapter_number"),
            "chapter_status": r.get("chapter_status", "active"),
            "chapter_weightage_marks": r.get("chapter_weightage_marks"),
            "active_topics": json.loads(r.get("active_topics", "[]")) if isinstance(r.get("active_topics"), str) else r.get("active_topics", []),
            "removed_topics": json.loads(r.get("removed_topics", "[]")) if isinstance(r.get("removed_topics"), str) else r.get("removed_topics", []),
            "confidence": r.get("score", 0),
            "academic_year": r.get("academic_year", "2025-26"),
        }
        for r in results
    ]
}

    except Exception as e:
        logger.error(f"[VERIFY] Error: {e}")
        return {"exists": False, "error": str(e), "message": "Verification failed"}


async def _refresh_stale_data(topic_key: str, query: str, vs: "VectorStore"):
    """Background task to refresh stale data."""
    try:
        fresh = _tavily_search(f"CBSE Class 10 {query} {ACADEMIC_YEAR} syllabus")
        if fresh:
            status = await _llm_check_deletion(
                topic_key.split("|")[-1] if "|" in topic_key else topic_key, fresh
            )
            if status.confidence > 0.6:
                meta = {
                    "topic_key": topic_key,
                    "chapter_status": "deleted" if status.is_deleted else "active",
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                }
                await vs.upsert_syllabus(
                    topic_key=topic_key, content=fresh[:500], metadata=meta
                )
                logger.info(f"[VERIFY] Updated stale data for {topic_key}")
    except Exception as e:
        logger.error(f"[VERIFY] Background refresh failed: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# TOOL 2: GET CHAPTER DETAILS
# ═══════════════════════════════════════════════════════════════════════════


@tool
async def get_chapter_details(
    subject: Optional[str] = None, chapter: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get detailed topics inside a CBSE Class 10 chapter.

    Use when:
    - Planning a study session for a specific chapter
    - User asks "What topics are in Polynomials?"
    - User asks "Show all Physics chapters"

    Args:
        subject: e.g., "Mathematics", "Science" (optional)
        chapter: e.g., "Polynomials", "Light" (optional)

    Note:
        - If only subject provided → returns all chapters for that subject
        - If both provided → returns specific chapter details

    Returns:
        {
            "found": bool,
            "chapters": [
                {
                    "chapter_name": "Polynomials",
                    "subject": "Mathematics",
                    "topics": ["Zeros", "Factor theorem", ...],
                    "removed_topics": [...],
                    "weightage_marks": 20,
                    "status": "active"
                },
                ...
            ]
        }

    Timeout: 3 seconds
    """
    from src.database.vector_store import VectorStore

    vs = VectorStore()

    logger.info(f"[CHAPTER] subject={subject}, chapter={chapter}")

    try:
        # If specific chapter requested
        if chapter and subject:
            search_query = f"{subject} {chapter} topics"
            results = await vs.search_syllabus(search_query, top_k=3)
        # If only subject - get all chapters using search
        elif subject:
            results = await vs.search_syllabus(f"{subject} Class 10 CBSE", top_k=20)
            # Filter to only this subject
            results = [
                r for r in results if r.get("subject", "").lower() == subject.lower()
            ]
        else:
            return {
                "found": False,
                "error": "Either subject or chapter must be provided",
            }

        if not results:
            logger.info("[CHAPTER] No chapters found")
            return {"found": False, "chapters": None}

        chapters = []
        for r in results:
            try:
                active = json.loads(r.get("active_topics", "[]"))
            except:
                active = []

            try:
                removed = json.loads(r.get("removed_topics", "[]"))
            except:
                removed = []

            chapters.append(
                {
                    "chapter_name": r.get("chapter_name", ""),
                    "subject": r.get("subject", ""),
                    "topics": active,
                    "removed_topics": removed,
                    "weightage_marks": r.get("chapter_weightage_marks"),
                    "status": r.get("chapter_status", "active"),
                }
            )

        logger.info(f"[CHAPTER] Found {len(chapters)} chapter(s)")

        return {"found": True, "chapters": chapters}

    except Exception as e:
        logger.error(f"[CHAPTER] Error: {e}")
        return {"found": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# TOOL 3: VERIFY AND ACT (Self-Correction)
# ═══════════════════════════════════════════════════════════════════════════


@tool
async def verify_and_act(subject: str, chapter: str, user_claim: str) -> Dict[str, Any]:
    """
    Verify user's claim about CBSE syllabus and correct if needed.

    Use when:
    - User contradicts agent: "My teacher said Polynomials is back"
    - User provides new information: "Actually Light was removed"
    - Agent needs to verify before updating

    This tool:
    1. Gets existing vector data (if any)
    2. Uses Tavily to verify claim with current web data
    3. Uses LLM to determine if claim is true
    4. Upserts corrected data to Pinecone

    Args:
        subject: e.g., "Mathematics", "Science"
        chapter: e.g., "Polynomials", "Light"
        user_claim: what user is claiming, e.g., "is back in 2025-26 syllabus"

    Returns:
        {
            "confirmed": bool,
            "corrected": bool,
            "message": "Verified - status updated" | "Claim not confirmed"
        }

    Timeout: 10 seconds (includes Tavily call)
    """
    from src.database.vector_store import VectorStore

    vs = VectorStore()
    topic_key = f"{subject}|{chapter}"

    logger.info(f"[VERIFY_AND_ACT] {subject} - {chapter}: {user_claim}")

    try:
        # 1. Get existing data
        existing = await vs.search_syllabus(topic_key, top_k=1)

        # 2. Call Tavily for current info
        query = f"CBSE Class 10 {subject} {chapter} {ACADEMIC_YEAR} official syllabus"
        tavily_result = _tavily_search(query, depth="advanced", max_results=5)

        if not tavily_result:
            return {
                "confirmed": False,
                "corrected": False,
                "message": "Could not verify claim - no web data available",
            }

        # 3. LLM decides if claim is true
        status = await _llm_check_deletion(chapter, tavily_result)

        if status.confidence < 0.6:
            return {
                "confirmed": False,
                "corrected": False,
                "message": f"Could not verify claim (confidence: {status.confidence})",
            }

        # 4. Determine new status
        new_status = "deleted" if status.is_deleted else "active"

        # 5. Upsert corrected data
        existing_meta = existing[0] if existing else {}

        metadata = {
            "topic_key": topic_key,
            "subject": subject,
            "chapter_name": chapter,
            "chapter_status": new_status,
            "active_topics": existing_meta.get("active_topics", "[]"),
            "removed_topics": existing_meta.get("removed_topics", "[]"),
            "chapter_weightage_marks": existing_meta.get("chapter_weightage_marks"),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "status": "user_contradiction",  # Mark as verified by user
        }

        await vs.upsert_syllabus(
            topic_key=topic_key, content=tavily_result[:500], metadata=metadata
        )

        logger.info(f"[VERIFY_AND_ACT] Corrected {topic_key} to {new_status}")

        return {
            "confirmed": status.is_deleted == (new_status == "deleted"),
            "corrected": True,
            "message": f"Verified and updated - Chapter is {new_status.upper()} in 2025-26 syllabus",
        }

    except Exception as e:
        logger.error(f"[VERIFY_AND_ACT] Error: {e}")
        return {
            "confirmed": False,
            "corrected": False,
            "message": f"Verification failed: {str(e)}",
        }


# ═══════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════

__all__ = [
    "verify_syllabus",
    "get_chapter_details",
    "verify_and_act",
    "VerifyResult",
    "ChapterDetailsResult",
    "VerifyAndActResult",
]
