"""Conversation history compression for live chat threads.

This layer is for continuity only. It must never replace source-of-truth state
such as the Intake contract, active plan, progress, calendar, or learner memory.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage


RAW_RECENT_MESSAGE_LIMIT = 20
HARD_RAW_MESSAGE_LIMIT = 40


SUMMARY_HEADER = "[CONVERSATION SUMMARY]"


@dataclass(frozen=True)
class CompressionResult:
    summary: str
    recent_messages: List[BaseMessage]
    removed_messages: List[BaseMessage]
    compressed: bool


def _message_role(message: BaseMessage) -> str | None:
    if isinstance(message, HumanMessage):
        return "User"
    if isinstance(message, AIMessage):
        return "Assistant"
    return None


def _compact_text(value: object) -> str:
    text = str(value or "").strip()
    return " ".join(text.split())


def _summary_lines(summary: str | None) -> list[str]:
    lines = []
    for raw in (summary or "").splitlines():
        line = raw.strip()
        if not line or line == SUMMARY_HEADER:
            continue
        if line.startswith("- "):
            lines.append(line)
        else:
            lines.append(f"- {line}")
    return lines


def _messages_to_lines(messages: Iterable[BaseMessage]) -> list[str]:
    lines: list[str] = []
    for message in messages:
        role = _message_role(message)
        if role is None:
            continue
        text = _compact_text(getattr(message, "content", ""))
        if not text:
            continue
        lines.append(f"- {role}: {text}")
    return lines


def compress_chat_history(
    messages: list[BaseMessage],
    existing_summary: str | None = None,
    *,
    recent_limit: int = RAW_RECENT_MESSAGE_LIMIT,
) -> CompressionResult:
    """Return a rolling summary plus the recent raw messages to keep.

    The summary is intentionally extractive and deterministic. It preserves
    useful conversational continuity without trying to infer durable facts.
    """

    if len(messages) <= recent_limit:
        return CompressionResult(
            summary=(existing_summary or "").strip(),
            recent_messages=list(messages),
            removed_messages=[],
            compressed=False,
        )

    split_at = len(messages) - recent_limit
    older_messages = list(messages[:split_at])
    recent_messages = list(messages[split_at:])

    lines = _summary_lines(existing_summary)
    lines.extend(_messages_to_lines(older_messages))

    summary = ""
    if lines:
        summary = SUMMARY_HEADER + "\n" + "\n".join(lines)

    return CompressionResult(
        summary=summary,
        recent_messages=recent_messages,
        removed_messages=older_messages,
        compressed=True,
    )


def conversation_summary_message(summary: str | None) -> SystemMessage | None:
    """Build a system message that clearly marks summary as soft context."""

    text = (summary or "").strip()
    if not text:
        return None
    return SystemMessage(
        content=(
            f"{text}\n\n"
            "Use this only as compressed chat continuity. It does not override "
            "the Intake contract, active plan, progress truth, calendar, tools, "
            "or the latest user message."
        )
    )


def messages_with_summary(
    messages: list[BaseMessage],
    summary: str | None,
) -> list[BaseMessage]:
    """Return the worker/router message stack with summary injected first."""

    summary_message = conversation_summary_message(summary)
    if summary_message is None:
        return list(messages or [])
    return [summary_message, *list(messages or [])]
