"""Trigger-driven learner-memory updates.

Normal chat history can happen every turn. Durable learner-memory synthesis
should run only after meaningful product events, such as an accepted plan.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

CHAT_MEMORY_REVIEW_EVERY_N = 10

MemorySynthesizer = Callable[[str, Any], Awaitable[bool]]
SessionOutcomeSynthesizer = Callable[[str, Any], Awaitable[bool]]
ChatMemoryExtractor = Callable[..., Awaitable[bool]]


def _openai_key_available() -> bool:
    return bool((os.getenv("OPENAI_API_KEY") or "").strip())


def should_count_chat_memory_turn(message: str) -> bool:
    """Cheap structural gate for chat-memory review counting.

    We intentionally avoid exact keyword matching here. The goal is only to
    skip tiny control chatter, not to decide memory meaning.
    """

    normalized = " ".join((message or "").split())
    if not normalized:
        return False
    word_count = len(normalized.split())
    if word_count >= 4:
        return True
    return len(normalized) >= 20


def _increment_chat_memory_turn_count(user_id: str) -> int:
    from src.database.neo4j import Neo4jManager

    neo = Neo4jManager()
    result = neo.graph.query(
        """MERGE (u:User {id: $user_id})
        SET u.chat_memory_turn_count = coalesce(u.chat_memory_turn_count, 0) + 1
        RETURN u.chat_memory_turn_count AS count""",
        {"user_id": user_id},
    )
    return result[0]["count"] if result else 1


async def review_chat_memory_after_message(
    *,
    user_id: str,
    message: str,
    vector_store: Any = None,
    extractor: ChatMemoryExtractor | None = None,
    turn_counter: Callable[[str], int] | None = None,
) -> bool:
    """Review chat for durable memory every N meaningful user turns."""

    if not user_id or not should_count_chat_memory_turn(message):
        return False

    if turn_counter is None:
        turn_counter = _increment_chat_memory_turn_count

    count = turn_counter(user_id)
    if count % CHAT_MEMORY_REVIEW_EVERY_N != 0:
        return False

    if extractor is None and not _openai_key_available():
        logger.info(
            "chat_memory review skipped for user_id=%s count=%s: OPENAI_API_KEY missing",
            user_id,
            count,
        )
        return False

    if vector_store is None:
        from src.database.vector_store import VectorStore

        vector_store = VectorStore()

    if extractor is None:
        from src.memory.chat_memory_extractor import extract_chat_memory

        extractor = extract_chat_memory

    return await extractor(
        user_id=user_id,
        message=message,
        vector_store=vector_store,
    )


def schedule_chat_memory_review(*, user_id: str, message: str) -> bool:
    """Schedule periodic chat-memory review after a meaningful user turn."""

    if not user_id or not should_count_chat_memory_turn(message):
        return False

    async def _run() -> None:
        try:
            await review_chat_memory_after_message(
                user_id=user_id,
                message=message,
            )
        except Exception as exc:
            logger.warning(
                "chat_memory review failed for user_id=%s error=%s",
                user_id,
                exc,
            )

    asyncio.create_task(_run())
    return True


async def synthesize_after_plan_accepted(
    *,
    user_id: str,
    vector_store: Any = None,
    synthesizer: MemorySynthesizer | None = None,
) -> bool:
    """Update learner memory after a plan is accepted.

    The accepted plan itself is already persisted as product truth. This trigger
    asks the learner-memory synthesizer to review episodic evidence and update
    soft planning guidance if there is enough signal.
    """

    if not user_id:
        return False

    if synthesizer is None and not _openai_key_available():
        logger.info(
            "plan_accepted memory synthesis skipped for user_id=%s: OPENAI_API_KEY missing",
            user_id,
        )
        return False

    if vector_store is None:
        from src.database.vector_store import VectorStore

        vector_store = VectorStore()

    if synthesizer is None:
        from src.memory.user_model_builder import force_analyze

        synthesizer = force_analyze

    return await synthesizer(user_id, vector_store)


def schedule_plan_accepted_memory_synthesis(*, user_id: str) -> bool:
    """Schedule non-blocking memory synthesis after plan acceptance."""

    if not user_id:
        return False

    if not _openai_key_available():
        logger.info(
            "plan_accepted memory synthesis not scheduled for user_id=%s: OPENAI_API_KEY missing",
            user_id,
        )
        return False

    async def _run() -> None:
        try:
            await synthesize_after_plan_accepted(user_id=user_id)
        except Exception as exc:
            logger.warning(
                "plan_accepted memory synthesis failed for user_id=%s error=%s",
                user_id,
                exc,
            )

    asyncio.create_task(_run())
    return True


async def synthesize_after_session_outcome(
    *,
    user_id: str,
    outcome: str,
    vector_store: Any = None,
    synthesizer: SessionOutcomeSynthesizer | None = None,
) -> bool:
    """Update learner memory after meaningful session progress evidence."""

    if not user_id:
        return False

    normalized_outcome = (outcome or "").strip().lower()
    if synthesizer is None and not _openai_key_available():
        logger.info(
            "session_outcome memory synthesis skipped for user_id=%s outcome=%s: OPENAI_API_KEY missing",
            user_id,
            normalized_outcome,
        )
        return False

    if vector_store is None:
        from src.database.vector_store import VectorStore

        vector_store = VectorStore()

    if synthesizer is None:
        if normalized_outcome in {"skipped", "missed"}:
            from src.memory.user_model_builder import force_analyze

            synthesizer = force_analyze
        else:
            from src.memory.user_model_builder import maybe_analyze_behavior

            synthesizer = maybe_analyze_behavior

    return await synthesizer(user_id, vector_store)


def schedule_session_outcome_memory_synthesis(
    *,
    user_id: str,
    outcome: str,
) -> bool:
    """Schedule learner-memory synthesis after session progress changes.

    Complete/partial/subtopic outcomes use the periodic learner-memory analyzer.
    Skipped/missed sessions are high-signal friction and force synthesis.
    """

    if not user_id:
        return False

    if not _openai_key_available():
        logger.info(
            "session_outcome memory synthesis not scheduled for user_id=%s outcome=%s: OPENAI_API_KEY missing",
            user_id,
            outcome,
        )
        return False

    async def _run() -> None:
        try:
            await synthesize_after_session_outcome(
                user_id=user_id,
                outcome=outcome,
            )
        except Exception as exc:
            logger.warning(
                "session_outcome memory synthesis failed for user_id=%s outcome=%s error=%s",
                user_id,
                outcome,
                exc,
            )

    asyncio.create_task(_run())
    return True
