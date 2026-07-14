"""Deterministic verification checks for Planner-generated study plans.

This file is the main quality gate between "LLM draft" and "acceptable plan".

Mental model:
- Planner can propose a schedule
- verifier checks whether that schedule obeys the locked contract
- commit should only happen after this verifier passes
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


def to_dict(value: Any) -> Dict[str, Any]:
    """Accept a Pydantic model or a plain dict."""

    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return value
    raise TypeError("plan/context must be a Pydantic model or dict")


def parse_time(date: str, time: str) -> datetime:
    """Parse a local date and HH:MM time into a naive datetime."""

    return datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")


def parse_interval(date: str, start: str, end: str) -> tuple[datetime, datetime]:
    """Parse a same-day or overnight time block.

    Intake stores sleep as blocks like 23:00-07:00 on the sleep-start date.
    Treat end <= start as crossing midnight so next-morning sessions are blocked.
    """

    start_dt = parse_time(date, start)
    end_dt = parse_time(date, end)
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)
    return start_dt, end_dt


def hours_between(start: datetime, end: datetime) -> float:
    """Return rounded hours between two datetimes."""

    return round((end - start).total_seconds() / 3600, 2)


def overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    """Return true when two datetime intervals overlap."""

    return a_start < b_end and a_end > b_start


def get_availability(context: Dict[str, Any]) -> Dict[str, Any]:
    """Return the availability section from planner context."""

    return context.get("availability") or {}


def get_daily_hours(context: Dict[str, Any]) -> Dict[str, float]:
    """Return normalized date-keyed daily study-hour budgets."""

    availability = get_availability(context)
    return {
        str(date): float(hours)
        for date, hours in (availability.get("daily_study_hours") or {}).items()
    }


def get_commitments(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten availability.time_blocks into one simple list."""

    availability = get_availability(context)
    commitments = availability.get("time_blocks") or {}
    rows: List[Dict[str, Any]] = []


    if isinstance(commitments, dict):
        for date, blocks in commitments.items():
            for block in blocks or []:
                start = block.get("start_time") or block.get("start")
                end = block.get("end_time") or block.get("end")
                if not start or not end:
                    continue
                rows.append(
                    {
                        "date": str(date),
                        "title": block.get("title") or "Commitment",
                        "start_time": start,
                        "end_time": end,
                        "source": block.get("source"),
                    }
                )
        return rows

    if isinstance(commitments, list):
        for block in commitments:
            date = block.get("date")
            start = block.get("start_time") or block.get("start")
            end = block.get("end_time") or block.get("end")
            if not date or not start or not end:
                continue
            rows.append(
                {
                    "date": str(date),
                    "title": block.get("title") or "Commitment",
                    "start_time": start,
                    "end_time": end,
                    "source": block.get("source"),
                }
            )

    return rows


def get_calendar_blocks(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return already-provided calendar blockers. This function never fetches.

    Planner trusts Intake/runtime to provide calendar truth; verifier only checks
    against blocks already present in the context packet.
    """

    raw_blocks = (
        context.get("blocked_slots")
        or context.get("calendar_blocks")
        or (get_availability(context).get("calendar_blocks") or [])
    )
    rows: List[Dict[str, Any]] = []

    for block in raw_blocks or []:
        date = block.get("date")
        start = block.get("start_time") or block.get("start")
        end = block.get("end_time") or block.get("end")
        if not date or not start or not end:
            continue
        rows.append(
            {
                "date": str(date),
                "title": block.get("title") or "Calendar blocker",
                "start_time": start,
                "end_time": end,
                "source": block.get("source") or "google_calendar",
            }
        )

    return rows


def get_available_time_windows(context: Dict[str, Any]) -> Dict[str, List[Dict[str, str]]]:
    """Return date-keyed legal placement windows from planner availability.

    This is the strongest scheduling boundary in verification: sessions must fit
    inside these windows, not just inside abstract daily-hour budgets.
    """

    availability = get_availability(context)
    raw_windows = (
        availability.get("available_time_windows")
        or context.get("available_time_windows")
        or {}
    )
    if not isinstance(raw_windows, dict):
        return {}

    windows: Dict[str, List[Dict[str, str]]] = {}
    for date, rows in raw_windows.items():
        normalized_rows: List[Dict[str, str]] = []
        for row in rows or []:
            start = row.get("start") or row.get("start_time")
            end = row.get("end") or row.get("end_time")
            if start and end:
                normalized_rows.append({"start": str(start), "end": str(end)})
        windows[str(date)] = normalized_rows
    return windows


def get_work_targets(context: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Return canonical work item targets from Intake study_items.

    These targets are the accounting contract the plan must satisfy.
    """

    targets: Dict[str, Dict[str, Any]] = {}
    for item in context.get("study_items") or []:
        work_id = item.get("scope_reference_key") or f"{item.get('subject')}::{item.get('chapter')}"
        targets[work_id] = {
            "scope_reference_key": item.get("scope_reference_key"),
            "subject": item.get("subject"),
            "chapter": item.get("chapter"),
            "estimated_hours": float(item.get("estimated_hours", 0) or 0),
        }
    return targets


def get_backlog_keys(context: Dict[str, Any]) -> set[str]:
    """Return all backlog subtopic keys locked by Intake work items."""

    keys = set()
    for item in context.get("study_items") or []:
        keys.update(key for key in item.get("remaining_subtopics", []) if key)
    return keys


def get_days(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return all days from a plan dictionary."""

    return plan.get("days") or []


def get_sessions(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return flattened session rows with their parent date and day."""

    rows = []
    for day in get_days(plan):
        for session in day.get("sessions") or []:
            rows.append({"date": day.get("date"), "day": day, "session": session})
    return rows


def work_id_for_allocation(allocation: Dict[str, Any], targets: Dict[str, Dict[str, Any]]) -> Optional[str]:
    """Match a session allocation back to a locked work-item target."""

    subject = allocation.get("subject")
    chapter = allocation.get("chapter")
    matches = [
        work_id
        for work_id, target in targets.items()
        if target.get("subject") == subject and target.get("chapter") == chapter
    ]
    if len(matches) == 1:
        return matches[0]

    chapter_matches = [
        work_id for work_id, target in targets.items() if target.get("chapter") == chapter
    ]
    if len(chapter_matches) == 1:
        return chapter_matches[0]

    return None


def check_plan_dates(plan: Dict[str, Any], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check that plan days cover the locked goal date range exactly."""

    goal = context.get("goal") or {}
    start = goal.get("start_date")
    end = goal.get("end_date")
    if not start or not end:
        return []

    try:
        cursor = datetime.strptime(start, "%Y-%m-%d").date()
        end_date = datetime.strptime(end, "%Y-%m-%d").date()
    except Exception:
        return []

    expected = []
    while cursor <= end_date:
        expected.append(cursor.isoformat())
        cursor += timedelta(days=1)

    present = {day.get("date") for day in get_days(plan)}
    missing = [date for date in expected if date not in present]
    if not missing:
        return []

    return [
        {
            "type": "missing_plan_dates",
            "dates": missing,
            "message": "Plan must include every date from goal.start_date to goal.end_date, even empty days.",
        }
    ]


def check_time_math(plan: Dict[str, Any], now: datetime) -> List[Dict[str, Any]]:
    """Check session durations, chronological order, and past-time placement."""

    errors = []

    for row in get_sessions(plan):
        date = row["date"]
        session = row["session"]
        title = session.get("title")
        start = session.get("start_time")
        end = session.get("end_time")

        if not date or not start or not end:
            errors.append(
                {
                    "type": "missing_time_fields",
                    "date": date,
                    "session": title,
                    "message": "Session needs date, start_time, and end_time.",
                }
            )
            continue

        try:
            start_dt = parse_time(date, start)
            end_dt = parse_time(date, end)
        except Exception as exc:
            errors.append(
                {
                    "type": "invalid_time_format",
                    "date": date,
                    "session": title,
                    "message": str(exc),
                }
            )
            continue

        actual_hours = hours_between(start_dt, end_dt)
        estimated_hours = float(session.get("estimated_hours", 0) or 0)

        if actual_hours <= 0:
            errors.append(
                {
                    "type": "invalid_session_duration",
                    "date": date,
                    "session": title,
                    "message": "Session end_time must be after start_time.",
                }
            )
            continue

        if abs(actual_hours - estimated_hours) > 0.01:
            errors.append(
                {
                    "type": "time_mismatch",
                    "date": date,
                    "session": title,
                    "expected_hours": actual_hours,
                    "reported_hours": estimated_hours,
                    "message": f"{start}-{end} is {actual_hours}h, but estimated_hours says {estimated_hours}h.",
                }
            )

        if start_dt <= now:
            errors.append(
                {
                    "type": "session_in_past",
                    "date": date,
                    "session": title,
                    "start_time": start,
                    "current_datetime": now.strftime("%Y-%m-%d %H:%M"),
                    "message": "Session starts before or at the current time.",
                }
            )

    return errors


def check_daily_hours(plan: Dict[str, Any], daily_hours: Dict[str, float]) -> List[Dict[str, Any]]:
    """Check that each day respects daily_study_hours."""

    errors = []
    totals = defaultdict(float)

    for row in get_sessions(plan):
        totals[row["date"]] += float(row["session"].get("estimated_hours", 0) or 0)

    for day in get_days(plan):
        date = day.get("date")
        reported = float(day.get("total_hours", 0) or 0)
        calculated = round(totals[date], 2)
        allowed = daily_hours.get(date)

        if abs(reported - calculated) > 0.01:
            errors.append(
                {
                    "type": "day_total_mismatch",
                    "date": date,
                    "reported_hours": reported,
                    "calculated_hours": calculated,
                    "message": "Day total_hours must equal the sum of its session estimated_hours.",
                }
            )

        if allowed is not None and calculated > allowed + 0.01:
            errors.append(
                {
                    "type": "daily_hours_exceeded",
                    "date": date,
                    "allowed_hours": allowed,
                    "scheduled_hours": calculated,
                    "message": f"Scheduled {calculated}h, but daily_study_hours is {allowed}h.",
                }
            )

    return errors


def check_raw_windows(plan: Dict[str, Any], raw_windows: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Check legacy raw_free_window constraints when provided."""

    errors = []

    for row in get_sessions(plan):
        date = row["date"]
        session = row["session"]
        start = session.get("start_time")
        end = session.get("end_time")
        if not date or not start or not end or date not in raw_windows:
            continue

        try:
            session_start = parse_time(date, start)
            session_end = parse_time(date, end)
        except Exception:
            continue

        fits = False
        allowed = []
        for window in raw_windows.get(date, []):
            window_start = parse_time(date, window["start_time"])
            window_end = parse_time(date, window["end_time"])
            allowed.append(f"{window['start_time']}-{window['end_time']}")
            if session_start >= window_start and session_end <= window_end:
                fits = True
                break

        if not fits:
            errors.append(
                {
                    "type": "outside_raw_window",
                    "date": date,
                    "session": session.get("title"),
                    "scheduled": f"{start}-{end}",
                    "allowed_windows": allowed,
                    "message": "Session is not fully inside one raw_free_window.",
                }
            )

    return errors


def check_available_time_windows(
    plan: Dict[str, Any],
    available_time_windows: Dict[str, List[Dict[str, str]]],
) -> List[Dict[str, Any]]:
    """Reject sessions that are not fully inside a legal available window."""

    if not available_time_windows:
        return []

    errors = []
    for row in get_sessions(plan):
        date = row["date"]
        session = row["session"]
        start = session.get("start_time")
        end = session.get("end_time")
        if not date or not start or not end:
            continue

        try:
            session_start = parse_time(date, start)
            session_end = parse_time(date, end)
        except Exception:
            continue

        allowed_windows = available_time_windows.get(date, [])
        allowed_labels = [
            f"{window['start']}-{window['end']}"
            for window in allowed_windows
            if window.get("start") and window.get("end")
        ]
        fits = False
        for window in allowed_windows:
            try:
                window_start = parse_time(date, window["start"])
                window_end = parse_time(date, window["end"])
            except Exception:
                continue
            if session_start >= window_start and session_end <= window_end:
                fits = True
                break

        if not fits:
            errors.append(
                {
                    "type": "available_window_conflict",
                    "date": date,
                    "session": session.get("title"),
                    "scheduled": f"{start}-{end}",
                    "allowed_windows": allowed_labels,
                    "message": "Session is not fully inside availability.available_time_windows.",
                }
            )

    return errors


def check_session_overlaps(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Reject sessions that overlap each other on the same date."""

    errors = []

    sessions_by_date: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in get_sessions(plan):
        date = row["date"]
        session = row["session"]
        start = session.get("start_time")
        end = session.get("end_time")
        if not date or not start or not end:
            continue

        try:
            start_dt = parse_time(date, start)
            end_dt = parse_time(date, end)
        except Exception:
            continue

        sessions_by_date[str(date)].append(
            {
                "title": session.get("title"),
                "start_time": start,
                "end_time": end,
                "start_dt": start_dt,
                "end_dt": end_dt,
            }
        )

    for date, sessions in sessions_by_date.items():
        valid_sessions = [
            session
            for session in sessions
            if session["end_dt"] > session["start_dt"]
        ]
        valid_sessions.sort(key=lambda session: session["start_dt"])

        for previous, current in zip(valid_sessions, valid_sessions[1:]):
            if overlaps(
                previous["start_dt"],
                previous["end_dt"],
                current["start_dt"],
                current["end_dt"],
            ):
                errors.append(
                    {
                        "type": "session_overlap",
                        "date": date,
                        "session": current.get("title"),
                        "conflicting_session": previous.get("title"),
                        "session_time": f"{current['start_time']}-{current['end_time']}",
                        "conflicting_time": f"{previous['start_time']}-{previous['end_time']}",
                        "message": "Sessions on the same date must not overlap each other.",
                    }
                )

    return errors


def check_commitments(plan: Dict[str, Any], commitments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Reject sessions that overlap manual commitments."""

    errors = []

    for row in get_sessions(plan):
        date = row["date"]
        session = row["session"]
        start = session.get("start_time")
        end = session.get("end_time")
        if not date or not start or not end:
            continue

        try:
            session_start, session_end = parse_interval(date, start, end)
        except Exception:
            continue

        for commitment in commitments:
            try:
                block_start, block_end = parse_interval(
                    commitment["date"],
                    commitment["start_time"],
                    commitment["end_time"],
                )
            except Exception:
                continue
            if overlaps(session_start, session_end, block_start, block_end):
                errors.append(
                    {
                        "type": "commitment_conflict",
                        "date": date,
                        "session": session.get("title"),
                        "commitment": commitment.get("title"),
                        "session_time": f"{start}-{end}",
                        "commitment_time": f"{commitment['start_time']}-{commitment['end_time']}",
                        "message": (
                            f"Session overlaps {commitment.get('title') or 'commitment'} "
                            f"from {commitment['start_time']}-{commitment['end_time']}."
                        ),
                    }
                )

    return errors


def check_calendar_blocks(plan: Dict[str, Any], calendar_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Reject sessions overlapping already-supplied calendar blockers."""

    if not calendar_blocks:
        return []

    errors = []

    for row in get_sessions(plan):
        date = row["date"]
        session = row["session"]
        start = session.get("start_time")
        end = session.get("end_time")
        if not date or not start or not end:
            continue

        try:
            session_start, session_end = parse_interval(date, start, end)
        except Exception:
            continue

        for block in calendar_blocks:
            try:
                block_start, block_end = parse_interval(
                    block["date"],
                    block["start_time"],
                    block["end_time"],
                )
            except Exception:
                continue

            if overlaps(session_start, session_end, block_start, block_end):
                errors.append(
                    {
                        "type": "calendar_conflict",
                        "date": date,
                        "session": session.get("title"),
                        "calendar_block": block.get("title"),
                        "session_time": f"{start}-{end}",
                        "calendar_time": f"{block['start_time']}-{block['end_time']}",
                        "message": (
                            f"Session overlaps calendar blocker {block.get('title') or 'Calendar blocker'} "
                            f"from {block['start_time']}-{block['end_time']}."
                        ),
                    }
                )

    return errors


def check_deadline(plan: Dict[str, Any], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Reject sessions ending after the locked goal deadline.

    This is separate from commitments because goal.deadline_datetime is a contract
    cutoff, not just a busy block.
    """

    deadline_datetime = (context.get("goal") or {}).get("deadline_datetime")
    if not deadline_datetime:
        return []

    try:
        deadline = datetime.fromisoformat(str(deadline_datetime).replace("Z", "+00:00"))
        deadline = deadline.replace(tzinfo=None)
    except Exception:
        return [
            {
                "type": "invalid_deadline_datetime",
                "deadline_datetime": deadline_datetime,
                "message": "goal.deadline_datetime must be a valid ISO datetime.",
            }
        ]

    errors = []
    for row in get_sessions(plan):
        date = row["date"]
        session = row["session"]
        start = session.get("start_time")
        end = session.get("end_time")
        if not date or not start or not end:
            continue

        try:
            session_end = parse_time(date, end)
        except Exception:
            continue

        if session_end > deadline:
            errors.append(
                {
                    "type": "deadline_conflict",
                    "date": date,
                    "session": session.get("title"),
                    "session_time": f"{start}-{end}",
                    "deadline_datetime": deadline_datetime,
                    "message": "Session ends after goal.deadline_datetime.",
                }
            )

    return errors


def check_work_totals(plan: Dict[str, Any], targets: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Check that session allocations match locked work-item target hours."""

    errors = []
    totals = defaultdict(float)

    for row in get_sessions(plan):
        session = row["session"]
        allocated_total = 0.0
        unknown_allocations = []

        for allocation in session.get("allocated_hours") or []:
            hours = float(allocation.get("hours", 0) or 0)
            allocated_total += hours
            work_id = work_id_for_allocation(allocation, targets)
            if work_id:
                totals[work_id] += hours
            else:
                unknown_allocations.append(allocation)

        estimated = float(session.get("estimated_hours", 0) or 0)
        if abs(round(allocated_total, 2) - estimated) > 0.01:
            errors.append(
                {
                    "type": "session_allocation_mismatch",
                    "date": row["date"],
                    "session": session.get("title"),
                    "estimated_hours": estimated,
                    "allocated_hours": round(allocated_total, 2),
                    "message": "Session allocated_hours must sum to estimated_hours.",
                }
            )

        for allocation in unknown_allocations:
            errors.append(
                {
                    "type": "unknown_work_item_allocation",
                    "date": row["date"],
                    "session": session.get("title"),
                    "allocation": allocation,
                    "message": "allocated_hours item does not match any context.study_items entry.",
                }
            )

    for work_id, target in targets.items():
        expected = round(float(target["estimated_hours"]), 2)
        actual = round(totals[work_id], 2)
        if abs(actual - expected) > 0.01:
            errors.append(
                {
                    "type": "work_total_mismatch",
                    "target_key": work_id,
                    "expected_hours": expected,
                    "allocated_hours": actual,
                    "message": f"Allocated {actual}h, but target is {expected}h.",
                }
            )

    return errors


def check_backlog_keys(plan: Dict[str, Any], known_keys: set[str]) -> List[Dict[str, Any]]:
    """Reject content match keys that were not locked by Intake."""

    if not known_keys:
        return []

    errors = []
    for row in get_sessions(plan):
        session = row["session"]
        keys = set(session.get("backlog_match_keys") or [])
        for content in session.get("contents") or []:
            if content.get("match_key"):
                keys.add(content["match_key"])

        for key in sorted(keys):
            if key not in known_keys:
                errors.append(
                    {
                        "type": "unknown_backlog_key",
                        "date": row["date"],
                        "session": session.get("title"),
                        "key": key,
                        "message": "Backlog key is not present in study_items.remaining_subtopics.",
                    }
                )

    return errors


def check_plan_total(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check that plan.total_hours equals the sum of all sessions."""

    reported = float(plan.get("total_hours", 0) or 0)
    calculated = round(
        sum(float(row["session"].get("estimated_hours", 0) or 0) for row in get_sessions(plan)),
        2,
    )
    if abs(reported - calculated) <= 0.01:
        return []
    return [
        {
            "type": "plan_total_mismatch",
            "reported_hours": reported,
            "calculated_hours": calculated,
            "message": "Plan total_hours must equal the sum of all session estimated_hours.",
        }
    ]


def build_summary(plan: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Build a compact verifier summary for logs and repair prompts."""

    scheduled_total = round(
        sum(float(row["session"].get("estimated_hours", 0) or 0) for row in get_sessions(plan)),
        2,
    )
    required_total = round(
        sum(float(item.get("estimated_hours", 0) or 0) for item in context.get("study_items") or []),
        2,
    )
    return {
        "days_checked": len(get_days(plan)),
        "sessions_checked": len(get_sessions(plan)),
        "scheduled_total_hours": scheduled_total,
        "required_total_hours": required_total,
    }


def verify_plan(
    plan: Any,
    context: Dict[str, Any],
    now: Optional[str] = None,
) -> Dict[str, Any]:
    """Verify a planner output against the same context packet the LLM saw."""

    plan_dict = to_dict(plan)
    context_dict = to_dict(context)
    now_dt = datetime.strptime(now, "%Y-%m-%d %H:%M") if now else datetime.now()

    errors: List[Dict[str, Any]] = []
    errors += check_plan_dates(plan_dict, context_dict)
    errors += check_time_math(plan_dict, now_dt)
    errors += check_daily_hours(plan_dict, get_daily_hours(context_dict))
    errors += check_available_time_windows(
        plan_dict,
        get_available_time_windows(context_dict),
    )
    errors += check_session_overlaps(plan_dict)
    errors += check_commitments(plan_dict, get_commitments(context_dict))
    errors += check_calendar_blocks(plan_dict, get_calendar_blocks(context_dict))
    errors += check_deadline(plan_dict, context_dict)
    errors += check_work_totals(plan_dict, get_work_targets(context_dict))
    errors += check_backlog_keys(plan_dict, get_backlog_keys(context_dict))
    errors += check_plan_total(plan_dict)

    return {
        "passed": not errors,
        "error_count": len(errors),
        "errors": errors,
        "summary": build_summary(plan_dict, context_dict),
    }
