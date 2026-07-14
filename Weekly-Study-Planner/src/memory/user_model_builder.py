"""
user_model_builder.py
Build lean learner-memory records from episodic evidence.
"""

import asyncio
import json
import logging
import os

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langsmith import traceable


load_dotenv()

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "skedioai-supervisor-v2"
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY", "")

logger = logging.getLogger(__name__)

ANALYZE_EVERY_N = 5

SYSTEM_PROMPT = """You are the learner-memory synthesizer for a student planning system.

Your role is to update an existing learner model using episodic evidence.
You must preserve uncertainty, avoid overfitting, and keep the output useful
for future planning.

You will receive:
1. EXISTING LEARNER MEMORY
2. FRESH EPISODIC EVIDENCE

Your task:
- Keep only planning-relevant durable patterns
- Prefer repeated tendencies over anecdotes
- Avoid turning weak signals into rigid rules
- Write short learner-memory records, not a personality essay

Important distinctions:
- Availability constraints explain when study is possible. They are not
  behavior memories by themselves.
- One missed session can be an event, but should not become a stable rule.
- If evidence is mixed or weak, omit the memory instead of forcing one.

Return ONLY valid JSON in this shape:
{
  "preference_memory": [
    "Short planning-relevant preference memories."
  ],
  "behavior_memory": [
    "Short repeated behavior tendencies with planning implications."
  ],
  "motivation_memory": [
    "Optional communication or encouragement preferences if supported."
  ],
  "system_notes": [
    "Optional safety notes that keep memory honest."
  ]
}

Rules:
- Do not include scores, confidence labels, or evidence counts
- Do not store exact active-plan facts as learner memory
- Do not create time-of-day bans unless repeated failures support it
- Prefer 0-2 strong memories per kind over many weak memories
- Each memory must be one concise sentence

Output only raw JSON. No prose. No markdown.
"""


def _clean_text_list(value) -> list[str]:
    """Normalize LLM output into a unique list of one-line memory records."""

    if not value:
        return []
    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, list):
        candidates = value
    else:
        return []

    cleaned = []
    seen = set()
    for item in candidates:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    return cleaned


def _format_existing_memory(memory: dict) -> str:
    context_items = memory.get("context") or []
    if not context_items:
        return "[]"

    lean_items = []
    for item in context_items:
        lean_items.append(
            {
                "kind": item.get("kind") or item.get("category") or "memory",
                "source": item.get("source") or "memory",
                "text": item.get("text") or "",
            }
        )
    return json.dumps(lean_items, indent=2)


def _format_episodic_logs(logs_raw: list[dict]) -> str:
    log_texts = []
    for match in logs_raw:
        meta = match.get("metadata", match)
        log_texts.append(
            {
                "event_type": meta.get("event_type") or meta.get("type"),
                "subject": meta.get("subject"),
                "topic": meta.get("topic") or meta.get("task_name"),
                "actual_hours": meta.get("actual_hours"),
                "estimated_hours": meta.get("estimated_hours"),
                "reason": meta.get("reason"),
                "date": meta.get("created_at", "")[:10]
                or str(meta.get("timestamp", ""))[:10],
                "day_of_week": meta.get("day_of_week"),
                "text": meta.get("text", ""),
            }
        )
    return json.dumps(log_texts, indent=2)


async def _store_model_outputs(user_id: str, vector_store, model: dict) -> None:
    kind_map = {
        "preference_memory": "preference",
        "behavior_memory": "behavior",
        "motivation_memory": "motivation",
        "system_notes": "system_note",
    }
    for field, kind in kind_map.items():
        for text in _clean_text_list(model.get(field)):
            await vector_store.upsert_context(
                user_id=user_id,
                text=text,
                metadata={"kind": kind, "source": "memory_synthesis"},
            )


@traceable(run_type="parser", name="get_completion_count")
def _get_completion_count(user_id: str) -> int:
    from src.database.neo4j import Neo4jManager

    neo = Neo4jManager()
    result = neo.graph.query(
        "MATCH (u:User {id: $user_id}) RETURN u.completion_count AS count",
        {"user_id": user_id},
    )
    return result[0]["count"] or 0 if result else 0


@traceable(run_type="parser", name="increment_completion_count")
def _increment_completion_count(user_id: str) -> int:
    from src.database.neo4j import Neo4jManager

    neo = Neo4jManager()
    result = neo.graph.query(
        """MATCH (u:User {id: $user_id})
        SET u.completion_count = coalesce(u.completion_count, 0) + 1
        RETURN u.completion_count AS count""",
        {"user_id": user_id},
    )
    return result[0]["count"] if result else 1


@traceable(run_type="parser", name="build_user_model")
async def build_user_model(user_id: str, vector_store) -> bool:
    """Build lean learner-memory records from episodic evidence."""

    logger.info("Building learner memory for %s...", user_id)

    try:
        old_context = await vector_store.load_full_memory(user_id)
        logs_raw = await vector_store.search_episodic(
            user_id=user_id,
            query="session completion reschedule behavior pattern",
            top_k=19,
        )

        if not logs_raw:
            logger.info("No episodic evidence yet for %s; skipping synthesis.", user_id)
            return False

        llm = ChatOpenAI(
            model="gpt-4.1-mini",
            temperature=0.2,
            api_key=os.getenv("OPENAI_API_KEY"),
        )

        response = await llm.ainvoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(
                    content=f"""
EXISTING LEARNER MODEL (update this, don't ignore it):
{_format_existing_memory(old_context)}

FRESH EPISODIC EVIDENCE (use this to update above):
{_format_episodic_logs(logs_raw)}
"""
                ),
            ]
        )

        try:
            raw = response.content.replace("```json", "").replace("```", "").strip()
            model = json.loads(raw)
        except Exception as e:
            logger.error("Failed to parse LLM response: %s", e)
            return False

        await _store_model_outputs(user_id, vector_store, model)
        logger.info("Learner memory built for %s", user_id)
        return True

    except Exception as e:
        logger.error("Learner memory build failed: %s", e)
        import traceback

        traceback.print_exc()
        return False


@traceable(run_type="parser", name="maybe_analyze_behavior")
async def maybe_analyze_behavior(user_id: str, vector_store) -> bool:
    """Run the learner-memory synthesizer periodically."""

    count = _increment_completion_count(user_id)
    logger.info("Completion #%s for %s", count, user_id)
    if count % ANALYZE_EVERY_N == 0:
        return await build_user_model(user_id, vector_store)
    return False


@traceable(run_type="parser", name="force_analyze")
async def force_analyze(user_id: str, vector_store) -> bool:
    """Force learner-memory synthesis. Useful in offline flows/tests."""

    return await build_user_model(user_id, vector_store)


async def main():
    from src.database.vector_store import VectorStore

    vs = VectorStore()
    await build_user_model("test_intake_memory_00159", vs)


if __name__ == "__main__":
    asyncio.run(main())
