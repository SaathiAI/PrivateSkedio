"""
Streaming and message-surface helpers for supervisor agents.

This module keeps UI streaming complexity out of the supervisor graph.
It should not decide routing, mutate worker state, or expose worker internals.
"""

import asyncio
from typing import Any, List

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.config import get_stream_writer


def extract_worker_reply_text(messages: List[BaseMessage]) -> str:
    """Extract the final user-visible reply text from a worker transcript."""

    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content and not getattr(msg, "tool_calls", None):
            return str(msg.content).strip()
    return ""


def chunk_to_text(content: Any) -> str:
    """Best-effort text extraction from streamed LLM chunk content."""

    if not content:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
        return "".join(parts)
    return str(content)


def get_writer_or_none():
    """Return LangGraph custom stream writer when available."""

    try:
        return get_stream_writer()
    except Exception:
        return None


def emit_user_facing_chunk(writer, text: str) -> None:
    """Push one user-facing text chunk to the graph stream."""

    if writer and text:
        writer({"event": "user_facing_chunk", "text": text})


async def stream_llm_text(llm, messages: List[BaseMessage], writer) -> str:
    """Stream an LLM reply while accumulating the final text."""

    chunks: List[str] = []
    async for chunk in llm.astream(messages):
        text = chunk_to_text(getattr(chunk, "content", ""))
        if not text:
            continue
        chunks.append(text)
        emit_user_facing_chunk(writer, text)
    return "".join(chunks).strip()


async def stream_plain_text(text: str, writer, chunk_size: int = 24) -> str:
    """Emit an already-available reply in small chunks for the UI/CLI."""

    final_text = str(text or "").strip()
    if not final_text:
        return ""

    if writer:
        for idx in range(0, len(final_text), chunk_size):
            emit_user_facing_chunk(writer, final_text[idx : idx + chunk_size])
            await asyncio.sleep(0)

    return final_text
