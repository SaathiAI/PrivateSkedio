"""Extract durable learner memories from selected chat messages.

This module is intentionally trigger-driven. Normal chat history can be saved
every turn, but this extractor should only run for meaningful memory moments
such as accepted plan changes, periodic chat review, or other explicit product
triggers.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI


load_dotenv()

logger = logging.getLogger(__name__)

MEMORY_KINDS = {"preference", "behavior", "academic", "motivation", "system_note"}

SYSTEM_PROMPT = """You extract durable learner memory for a study-planning app.

You receive:
1. A user chat message
2. Existing memory records for the same user

Return ONLY raw JSON in this exact shape:
{
  "kind": "preference | behavior | academic | motivation | system_note | none",
  "text": "one merged memory sentence, or empty string"
}

Rules:
- Store only durable study-planning signals.
- Ignore casual chat, commands with no durable learner fact, jokes, and one-off frustration.
- Do not store raw chat.
- Do not include metadata, confidence, evidence count, or category.
- If useful memory already exists, merge the new signal with the old memory.
- Do not lose useful old memory when adding the new signal.
- Keep text as one concise sentence.
- Use "none" when nothing should be remembered.

Good memory examples:
- User prefers shorter study sessions.
- User prefers avoiding heavy Physics after tuition because they get sleepy.
- User struggles with Chemistry formula recall and may need spaced revision.
- User prefers direct concise encouragement over long motivational messages.
"""


def should_attempt_memory_extraction(message: str) -> bool:
    """Skip empty/tiny input only once a trigger has selected this message."""

    normalized = " ".join((message or "").lower().split())
    if not normalized:
        return False
    if len(normalized) < 2:
        return False
    return True


def _existing_memory_for_prompt(records: list[dict[str, Any]]) -> str:
    if not records:
        return "[]"
    lean = []
    for item in records:
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        lean.append(
            {
                "kind": str(item.get("kind") or "memory"),
                "source": str(item.get("source") or "memory"),
                "text": text,
            }
        )
    return json.dumps(lean, indent=2)


def _parse_extraction(raw: str) -> tuple[str, str]:
    cleaned = (raw or "").replace("```json", "").replace("```", "").strip()
    data = json.loads(cleaned)
    kind = str(data.get("kind") or "none").strip().lower().replace(" ", "_")
    text = str(data.get("text") or "").strip()
    if kind not in MEMORY_KINDS:
        return "none", ""
    if not text:
        return "none", ""
    return kind, text


async def extract_chat_memory(
    *,
    user_id: str,
    message: str,
    vector_store,
    llm: Any = None,
) -> bool:
    """Extract and upsert one merged learner memory from a user chat message."""

    if not should_attempt_memory_extraction(message):
        return False

    try:
        existing = await vector_store.get_all_context(user_id)
    except Exception:
        existing = []

    if llm is None:
        llm = ChatOpenAI(
            model="gpt-4.1-mini",
            temperature=0,
            api_key=os.getenv("OPENAI_API_KEY"),
        )

    try:
        response = await llm.ainvoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(
                    content=f"""
USER CHAT MESSAGE:
{message}

EXISTING LEARNER MEMORY:
{_existing_memory_for_prompt(existing)}
"""
                ),
            ]
        )
        kind, text = _parse_extraction(response.content)
        if kind == "none":
            return False
        return await vector_store.upsert_context(
            user_id=user_id,
            text=text,
            metadata={"kind": kind, "source": "chat"},
        )
    except Exception as exc:
        logger.warning("chat memory extraction failed for user_id=%s: %s", user_id, exc)
        return False
