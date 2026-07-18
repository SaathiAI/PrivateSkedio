"""Active-plan snapshot helpers for API and agent tools."""

from __future__ import annotations

import copy
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ACTIVE_PLAN_CACHE_TTL_SECONDS = int(os.getenv("ACTIVE_PLAN_CACHE_TTL_SECONDS", "10"))
ACTIVE_PLAN_STATUS_CACHE_TTL_SECONDS = int(
    os.getenv("ACTIVE_PLAN_STATUS_CACHE_TTL_SECONDS", "30")
)
_active_plan_status_cache: Dict[str, tuple[Dict[str, Any], float]] = {}
_active_plan_rows_cache: Dict[str, tuple[List[Dict[str, Any]], float]] = {}
_active_plan_snapshot_cache: Dict[str, tuple[Dict[str, Any], float]] = {}
_active_plan_cache_lock = threading.Lock()


def invalidate_active_plan_cache(user_id: Optional[str] = None) -> None:
    with _active_plan_cache_lock:
        if user_id is None:
            _active_plan_status_cache.clear()
            _active_plan_rows_cache.clear()
            _active_plan_snapshot_cache.clear()
            return
        _active_plan_status_cache.pop(user_id, None)
        _active_plan_rows_cache.pop(user_id, None)
        _active_plan_snapshot_cache.pop(user_id, None)


def _get_cached_entry(cache: Dict[str, tuple[Any, float]], user_id: str) -> Any:
    now = time.time()
    with _active_plan_cache_lock:
        cached = cache.get(user_id)
        if not cached:
            return None
        value, expires_at = cached
        if expires_at <= now:
            cache.pop(user_id, None)
            return None
        return copy.deepcopy(value)


def _set_cached_entry(
    cache: Dict[str, tuple[Any, float]],
    user_id: str,
    value: Any,
    *,
    ttl_seconds: int = ACTIVE_PLAN_CACHE_TTL_SECONDS,
) -> Any:
    expires_at = time.time() + ttl_seconds
    with _active_plan_cache_lock:
        cache[user_id] = (copy.deepcopy(value), expires_at)
    return copy.deepcopy(value)


def get_active_plan_status(
    user_id: str,
    neo4j=None,
    *,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    if not force_refresh:
        cached_status = _get_cached_entry(_active_plan_status_cache, user_id)
        if cached_status is not None:
            return cached_status

    if neo4j is None:
        from src.database.neo4j import Neo4jManager

        neo4j = Neo4jManager()

    status = neo4j.get_active_plan_status(user_id)
    return _set_cached_entry(
        _active_plan_status_cache,
        user_id,
        status,
        ttl_seconds=ACTIVE_PLAN_STATUS_CACHE_TTL_SECONDS,
    )


def get_active_plan_rows(
    user_id: str,
    neo4j=None,
    *,
    force_refresh: bool = False,
) -> List[Dict[str, Any]]:
    if not force_refresh:
        cached_rows = _get_cached_entry(_active_plan_rows_cache, user_id)
        if cached_rows is not None:
            return cached_rows

    if neo4j is None:
        from src.database.neo4j import Neo4jManager

        neo4j = Neo4jManager()

    raw_rows = neo4j.get_active_plan_sessions(user_id)
    return _set_cached_entry(_active_plan_rows_cache, user_id, raw_rows)


def get_active_plan_snapshot(
    user_id: str,
    neo4j=None,
    *,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    if not force_refresh:
        cached_snapshot = _get_cached_entry(_active_plan_snapshot_cache, user_id)
        if cached_snapshot is not None:
            return cached_snapshot

    raw_plan = get_active_plan_rows(user_id, neo4j, force_refresh=force_refresh)
    snapshot = build_active_plan_snapshot(raw_plan)
    return _set_cached_entry(_active_plan_snapshot_cache, user_id, snapshot)


def json_or_default(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return default
    return value


def content_name(content: Dict[str, Any]) -> str:
    return (
        content.get("canonical_name")
        or content.get("name")
        or content.get("match_key")
        or "Untitled content"
    )


def work_item_key(subject: str, chapter: str) -> str:
    subject = (subject or "").strip()
    chapter = (chapter or "").strip()
    return f"{subject}::{chapter}" if subject else chapter


def chapter_lookup_key(subject: str, chapter: str) -> str:
    return f"{(subject or '').strip().lower()}|{(chapter or '').strip().lower()}"


def parse_work_item_key(key: str) -> Dict[str, str]:
    if "::" in key:
        subject, chapter = key.split("::", 1)
        return {"subject": subject, "chapter": chapter}
    if "|" in key:
        subject, chapter = key.split("|", 1)
        return {"subject": subject, "chapter": chapter}
    return {"subject": "", "chapter": key}


def sanitize_intake_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Keep the locked contract, remove stale/live scheduling artifacts."""

    if not isinstance(snapshot, dict):
        return {}

    cleaned = dict(snapshot)
    cleaned.pop("availability_math", None)
    cleaned.pop("calendar_events_used", None)

    availability = cleaned.get("availability")
    if isinstance(availability, dict):
        availability = dict(availability)
        availability.pop("calendar_events_used", None)
        availability.pop("raw_free_windows", None)
        availability.pop("available_windows", None)
        availability.pop("candidate_study_windows", None)
        availability.pop("daily_available_hours", None)

        commitments = availability.get("time_blocks")
        if isinstance(commitments, dict):
            availability["time_blocks"] = {
                str(date): [
                    item
                    for item in (items or [])
                    if not isinstance(item, dict)
                    or item.get("source") not in {"google_calendar", "calendar"}
                ]
                for date, items in commitments.items()
            }
        elif isinstance(commitments, list):
            availability["time_blocks"] = [
                item
                for item in commitments
                if not isinstance(item, dict)
                or item.get("source") not in {"google_calendar", "calendar"}
            ]

        cleaned["availability"] = availability

    return cleaned


def build_work_item_targets(raw_plan: List[Dict[str, Any]]) -> Dict[str, float]:
    if not raw_plan:
        return {}

    first = raw_plan[0]
    targets = json_or_default(first.get("work_item_targets"), {})
    if targets:
        return {str(key): round(float(value or 0), 2) for key, value in targets.items()}

    legacy_targets = json_or_default(first.get("topic_time_estimates"), {})
    return {
        str(key): round(float(value or 0), 2)
        for key, value in (legacy_targets or {}).items()
    }


def group_active_plan_days(raw_plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    days_map: Dict[str, Dict[str, Any]] = {}
    seen_sessions = set()

    for row in raw_plan:
        day_date = str(row.get("date")) if row.get("date") else None
        if not day_date:
            continue

        if day_date not in days_map:
            days_map[day_date] = {
                "day_num": row.get("day_num"),
                "date": day_date,
                "capacity_hours": round(float(row.get("capacity_hours") or 0), 2),
                "total_hours": round(float(row.get("day_total_hours") or 0), 2),
                "sessions": [],
            }

        session_id = row.get("session_id")
        if not session_id or session_id in seen_sessions:
            continue
        seen_sessions.add(session_id)

        contents = []
        for raw_content in row.get("contents") or []:
            content = dict(raw_content)
            contents.append(
                {
                    "match_key": content.get("match_key"),
                    "name": content_name(content),
                    "subjects": content.get("subjects") or [],
                    "chapters": content.get("chapters") or [],
                    "type": content.get("type") or "subtopic",
                    "status": content.get("status") or "pending",
                    "time_spent": round(float(content.get("time_spent") or 0), 2),
                }
            )

        days_map[day_date]["sessions"].append(
            {
                "session_id": session_id,
                "title": row.get("session_title") or "Study Session",
                "session_type": row.get("session_type") or "chapter",
                "start_time": row.get("start_time"),
                "end_time": row.get("end_time"),
                "estimated_hours": round(float(row.get("estimated_hours") or 0), 2),
                "allocated_hours": json_or_default(row.get("allocated_hours"), []),
                "actual_time": round(float(row.get("actual_time") or 0), 2),
                "status": row.get("session_status") or "pending",
                "contents": contents,
            }
        )

    for day in days_map.values():
        day["sessions"].sort(key=lambda session: session.get("start_time") or "")

    return sorted(days_map.values(), key=lambda day: day.get("day_num") or 0)


def _work_item_meta_from_intake(
    intake_snapshot: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    meta = {}
    for item in intake_snapshot.get("study_items") or []:
        if not isinstance(item, dict):
            continue
        item_id = item.get("scope_reference_key") or work_item_key(
            item.get("subject") or "",
            item.get("chapter") or "",
        )
        meta[item_id] = {
            "subject": item.get("subject") or "",
            "chapter": item.get("chapter") or item_id,
            "reason": item.get("reason"),
            "intake_guidance": item.get("intake_guidance") or [],
            "remaining_subtopics": item.get("remaining_subtopics") or [],
        }
    return meta


def build_work_item_progress(
    raw_plan: List[Dict[str, Any]],
    days: List[Dict[str, Any]],
    intake_snapshot: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    targets = build_work_item_targets(raw_plan)
    intake_meta = _work_item_meta_from_intake(intake_snapshot)
    progress: Dict[str, Dict[str, Any]] = {}

    for key, estimated_hours in targets.items():
        parsed = parse_work_item_key(key)
        meta = intake_meta.get(key) or {}
        progress[key] = {
            "subject": meta.get("subject") or parsed["subject"],
            "chapter": meta.get("chapter") or parsed["chapter"],
            "total": round(float(estimated_hours or 0), 2),
            "spent": 0.0,
            "remaining": round(float(estimated_hours or 0), 2),
            "completed_subtopics": [],
            "pending_subtopics": [],
            "completed_match_keys": [],
            "pending_match_keys": [],
            "reason": meta.get("reason"),
            "intake_guidance": meta.get("intake_guidance") or [],
            "remaining_subtopics": meta.get("remaining_subtopics") or [],
        }

    def ensure_item(subject: str, chapter: str) -> Optional[str]:
        if not chapter:
            return None
        exact = work_item_key(subject, chapter)
        if exact in progress:
            return exact

        lookup = chapter_lookup_key(subject, chapter)
        for key, item in progress.items():
            if chapter_lookup_key(item.get("subject", ""), item.get("chapter", "")) == lookup:
                return key

        progress[exact] = {
            "subject": subject,
            "chapter": chapter,
            "total": 0.0,
            "spent": 0.0,
            "remaining": 0.0,
            "completed_subtopics": [],
            "pending_subtopics": [],
            "completed_match_keys": [],
            "pending_match_keys": [],
            "reason": None,
            "intake_guidance": [],
            "remaining_subtopics": [],
        }
        return exact

    for day in days:
        for session in day.get("sessions") or []:
            for content in session.get("contents") or []:
                subjects = content.get("subjects") or [""]
                chapters = content.get("chapters") or []
                subject = subjects[0] if subjects else ""
                for chapter in chapters:
                    key = ensure_item(subject, chapter)
                    if not key:
                        continue
                    item = progress[key]
                    name = content.get("name") or content.get("match_key")
                    match_key = content.get("match_key")
                    if content.get("status") == "done":
                        item["spent"] += float(content.get("time_spent") or 0)
                        if name and name not in item["completed_subtopics"]:
                            item["completed_subtopics"].append(name)
                        if match_key and match_key not in item["completed_match_keys"]:
                            item["completed_match_keys"].append(match_key)
                    else:
                        if name and name not in item["pending_subtopics"]:
                            item["pending_subtopics"].append(name)
                        if match_key and match_key not in item["pending_match_keys"]:
                            item["pending_match_keys"].append(match_key)

    for item in progress.values():
        item["spent"] = round(item["spent"], 2)
        item["remaining"] = round(max(float(item["total"]) - item["spent"], 0), 2)
        if item["remaining"] <= 0:
            item["status"] = "completed"
        elif item["spent"] > 0:
            item["status"] = "in_progress"
        else:
            item["status"] = "pending"

    return progress


def build_active_plan_snapshot(raw_plan: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build the rescheduler/API active-plan truth from Neo4j rows."""

    if not raw_plan:
        return {"has_plan": False, "plan_details": None}

    first = raw_plan[0]
    intake_snapshot = sanitize_intake_snapshot(
        json_or_default(first.get("intake_snapshot"), {})
    )
    days = group_active_plan_days(raw_plan)
    progress = build_work_item_progress(raw_plan, days, intake_snapshot)
    start_date = days[0]["date"] if days else None
    end_date = days[-1]["date"] if days else None

    plan_details = {
        "plan_id": first.get("plan_id"),
        "plan_name": first.get("plan_name"),
        "status": first.get("plan_status"),
        "total_hours": round(float(first.get("plan_total_hours") or 0), 2),
        "start_date": start_date,
        "end_date": end_date,
        "intake_snapshot": intake_snapshot,
        "days": days,
        "progress": {
            "work_item_budget": progress,
        },
    }

    return {
        "has_plan": True,
        "plan_details": plan_details,
    }


def build_mock_active_plan_snapshot() -> Dict[str, Any]:
    """Load the project dummy active plan used by local rescheduler smoke tests."""

    fixture_path = (
        Path(__file__).resolve().parents[2]
        / "data_models"
        / "rescheduler_demo_active_plan_snapshot.json"
    )
    if fixture_path.exists():
        try:
            return json.loads(fixture_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    return {"has_plan": False, "plan_details": None}
