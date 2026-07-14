import os
import json
import asyncio
import logging
import time
import functools
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from src.database.vector_store import VectorStore

logger = logging.getLogger(__name__)
ACADEMIC_YEAR = "2025-26"

vs = VectorStore()


def timer(func):
    """Decorator to time async and sync functions, prints raw time to terminal."""

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = await func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"[{func.__name__}] {elapsed:.3f}s")
        return result

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"[{func.__name__}] {elapsed:.3f}s")
        return result

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


class ChapterEntry(BaseModel):
    """Chapter entry structure for vector storage."""

    is_confirmed: bool = Field(
        description="True ONLY if the live web strictly confirms the student's claim."
    )
    topic_key: str = Field(
        description="MUST be strictly formatted as 'Subject|Chapter Name'. Example: 'Mathematics|Triangles'. Do not use abbreviations."
    )
    subject: str
    chapter_name: str
    chapter_number: Optional[int] = None
    subject_total_marks: Optional[int] = None
    chapter_weightage_marks: Optional[int] = None
    active_topics: List[str] = Field(default_factory=list)
    removed_topics: List[str] = Field(default_factory=list)
    search_text: str = Field(
        description="It is a search text which concludes your finding and a short summary about this chapter."
    )
    chapter_status: str = "active"
    status: str = Field(description="'active' or 'deleted' based on the new truth.")
    last_updated: str = ""


@timer
def tavily_search(query: str, depth: str = "basic", max_results: int = 4) -> str:
    """Tavily Search to return content to find the curiculum realated things"""

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
                [
                    f"[{r.get('url', '')}]\n{r.get('content', '')[:1000]}"
                    for r in results
                ]
            )
        return ""
    except Exception as e:
        logger.error(f"Tavily failed: {e}")
        return ""


@timer
def stale(updated_at: str, days: int = 30) -> bool:
    """Delete things which are stale currently not in use"""
    try:
        dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days > days
    except Exception:
        return True


@tool
async def semantic_search_tool(query: str):
    """
    Search Syllabus from the vectordb using semantic similarity.
    Use when user wants to find topics, explanations, or information about CBSE chapters.

    Args:
        query: Search query (e.g., "quadratic equations", "photosynthesis")

    Returns:
        Relevant syllabus entries matching the query
    """
    retrieved_info = await vs.search_syllabus(query, top_k=4)
    return retrieved_info


@tool
async def vector_filter_tool(subject: str = None, chapter_status: str = "Active"):
    """
    Filter syllabus by subject or chapter status.
    Use when user wants to:
    - Find all chapters of a subject ("show me physics chapters")
    - Filter by active/inactive status
    - Know chapter count or weightage

    Args:
        subject: Subject name (e.g., "Mathematics", "Science")
        chapter_status: Filter by status (default: "Active")

    Returns:
        Chapters matching the filter criteria
    """
    retrieved_info = await vs.vector_filter(
        subject=subject, chapter_status=chapter_status
    )
    return retrieved_info


@tool
async def verify_and_act(subject: str, chapter: str, user_claim: str):
    """
    Verify a user's claim about CBSE syllabus using Tavily + LLM, and update vector if confirmed.

    Use when:
    - User contradicts what agent said like:
        - User says "my teacher said Polynomials is back in syllabus"
        - User says "that chapter wasn't deleted"

    This tool:
    1. Gets existing vector data (if any)
    2. Uses one LLM call with Tavily to verify AND return complete ChapterEntry
    3. Upserts with same topic_key (same ID = overwrites existing)

    Args:
        subject: e.g. "Science", "Mathematics"
        chapter: e.g. "Periodic Classification", "Polynomials"
        user_claim: what user is claiming e.g. "chapter is back in 2025-26 syllabus"

    Returns:
        confirmed: bool
        updated_pinecone: bool
        message: what to tell the user
    """

    ts = datetime.now(timezone.utc).isoformat()

    topic_key = f"{subject}|{chapter}"

    logger.info(f"[SYLLABUS] CRAG verify: {subject} - {chapter}: {user_claim}")

    query = f"{subject} - {chapter} user has said {user_claim}"

    retrieved_info = await vs.search_syllabus(query, top_k=3)

    tavily_response = tavily_search(
        f"CBSE Class 10 {subject} {chapter} {ACADEMIC_YEAR} "
        f"official syllabus chapters topics weightage",
        depth="advanced",
        max_results=5,
    )

    if not tavily_response:
        return {
            "confirmed": False,
            "updated_pinecone": False,
            "message": "Couldn't verify. Want to add anyway?",
        }

    print("RETRIEVED INFO IS", retrieved_info)

    eval_prompt = f"""
    ### ROLE: Senior CBSE Curriculum Auditor (Academic Year {ACADEMIC_YEAR})
    
    ### CASE FILE:
    - **Subject**: {subject}
    - **Chapter**: {chapter}
    - **Student's Claim**: "{user_claim}"
    
    ### EVIDENCE:
    1. **Internal Memory (Vectordb)**: 
    {retrieved_info}
    
    2. **Live Official Intelligence (Tavily Search)**: 
    {tavily_response}
    
    ### INSTRUCTIONS:
    1. **Identify the Web Truth**: What does the Live Intelligence actually say about this topic for {ACADEMIC_YEAR} is it even a topic which subject is it in syllabus?
    2. **Evaluate Internal Memory**: Look at our Vectordb memory. Is it completely empty `[]`? Or does it contain outdated/wrong information compared to the live web?
    3. **The Database Trigger (`is_confirmed`)**: 
       - If Internal Memory is EMPTY `[]` -> MUST set `is_confirmed: True`.
       - If Internal Memory CONTRADICTS the live web -> MUST set `is_confirmed: True`.
       - If Internal Memory perfectly MATCHES the live web -> Set `is_confirmed: False`.
    4. **The Topic Key Rule (`topic_key`)**: You MUST generate the `topic_key` exactly as `Subject|Chapter Name`. 
       - Use a pipe `|` to separate them.
       - Fix any spelling mistakes the student made (e.g., if they say "Trianglesss", fix it to "Triangles").
       - Never use abbreviations (Use "Mathematics", not "Maths").
       - Example: `Mathematics|Triangles` or `Science|Light`.
    5. **Output Synthesis (`search_text`)**: Write a clear, peer-to-peer explanation for the student. Tell them if their claim was right or wrong based on the official web search.



    ### FINAL VERDICT:
    Does the official live search confirm the user's claim over our internal memory?
    """

    try:
        llm_verify = ChatOpenAI(
            model="openai/gpt-4o-mini",
            temperature=0,
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
        ).with_structured_output(ChapterEntry)

        result = await llm_verify.ainvoke(
            [
                SystemMessage(content=eval_prompt),
                HumanMessage(content=f""),
            ]
        )
        logger.info(f"Verified: {result}")

        clean_topic_key = (
            f"{result.subject.strip().title()}|{result.chapter_name.strip().title()}"
        )

        if result.is_confirmed:
            meta = {
                "topic_key": clean_topic_key,
                "subject": result.subject,
                "chapter_name": result.chapter_name,
                "chapter_number": result.chapter_number or 0,
                "subject_total_marks": result.subject_total_marks or 80,
                "chapter_weightage_marks": result.chapter_weightage_marks or 0,
                "active_topics": json.dumps(result.active_topics),
                "removed_topics": json.dumps(result.removed_topics),
                "search_text": result.search_text,
                "chapter_status": result.chapter_status,
                "status": "user_contradiction",
                "academic_year": ACADEMIC_YEAR,
                "last_updated": ts,
            }

            await vs.upsert_syllabus(
                topic_key=clean_topic_key,
                content=result.search_text,
                metadata=meta,
            )

            logger.info(
                f"[SYLLABUS] Updated vector: {topic_key} with status={result.chapter_status}"
            )

            return {
                "llm_approval": result.is_confirmed,
                "topic_key": clean_topic_key,
                "updated_pinecone": True,
                "chapter_status": result.chapter_status,
                "active_topics": result.active_topics,
                "removed_topics": result.removed_topics,
                "message": f"Confirmed: {result.search_text}",
            }

    except Exception as e:
        logger.error(f"LLM verification failed: {e}")
        return {
            "confirmed": False,
            "updated_pinecone": False,
            "message": "Verification failed. Proceed with caution.",
        }

    return {
        "match_key": result.topic_key,
        "llm_approval": result.is_confirmed,
        "updated_pinecone": False,
        "message": f"Exactly! My records already show that: {result.search_text}",
    }


if __name__ == "__main__":
    result = asyncio.run(
        verify_and_act.ainvoke(
            {
                "subject": "Science",
                "chapter": "I dont know",
                "user_claim": "my teacher said Chapter malnurition is  not present in the syllabus",
            }
        )
    )
    print(result)
