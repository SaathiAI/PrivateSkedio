from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Optional


feasibility_logger = logging.getLogger("src.services.intake_feasibility")
feasibility_logger.setLevel(logging.DEBUG)

_log_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "logs",
)
os.makedirs(_log_dir, exist_ok=True)
_log_path = os.path.join(_log_dir, "feasibility_check.log")

if not feasibility_logger.handlers:
    _file_handler = logging.FileHandler(_log_path, mode="a", encoding="utf-8")
    _file_handler.setLevel(logging.DEBUG)
    _file_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    )
    feasibility_logger.addHandler(_file_handler)


def _get(obj: Any, key: str, default=None):
    """Supports both dict and Pydantic/class objects."""
    if obj is None:
        return default

    if isinstance(obj, dict):
        return obj.get(key, default)

    return getattr(obj, key, default)


def _to_minutes(time_str: Optional[str]) -> Optional[int]:
    """
    Converts HH:MM to minutes.

    Examples:
    08:30 -> 510
    24:00 -> 1440
    """
    if not time_str:
        return None

    try:
        hh, mm = str(time_str).strip().split(":")[:2]
        hh = int(hh)
        mm = int(mm)

        if hh == 24 and mm == 0:
            return 1440

        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            return None

        return hh * 60 + mm

    except Exception:
        return None


def _minutes_to_time(minutes: int) -> str:
    """
    Converts minutes to HH:MM.

    Examples:
    510 -> 08:30
    1440 -> 24:00
    """
    minutes = max(0, min(1440, int(minutes)))

    if minutes == 1440:
        return "24:00"

    hh = minutes // 60
    mm = minutes % 60
    return f"{hh:02d}:{mm:02d}"


def _split_interval(start: int, end: int) -> list[tuple[int, int]]:
    """
    Handles normal + overnight intervals.

    08:00 -> 14:00 = [(480, 840)]
    22:00 -> 24:00 = [(1320, 1440)]
    23:00 -> 06:00 = [(1380, 1440), (0, 360)]
    """
    if start == end:
        return []

    if end > start:
        return [(start, end)]

    return [(start, 1440), (0, end)]


def _merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge overlapping intervals so blockers are not double-counted."""
    if not intervals:
        return []

    intervals = sorted(intervals)
    merged = [intervals[0]]

    for start, end in intervals[1:]:
        last_start, last_end = merged[-1]

        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))

    return merged


def _clip_interval(
    interval: tuple[int, int],
    window_start: int,
    window_end: int,
) -> Optional[tuple[int, int]]:
    """Keeps only the interval part inside usable day window."""
    start, end = interval

    clipped_start = max(start, window_start)
    clipped_end = min(end, window_end)

    if clipped_end <= clipped_start:
        return None

    return clipped_start, clipped_end


def _deadline_cutoff_for_day(deadline_datetime: Optional[str], day: str) -> Optional[int]:
    """
    If deadline is on this day, return deadline cutoff in minutes.

    Example:
    2026-06-11T18:00:00+05:30 -> 1080

    For exams, deadline_datetime should usually be exam START time,
    because study after the exam starts is no longer useful for that exam goal.
    """
    if not deadline_datetime:
        return None

    try:
        dt = datetime.fromisoformat(deadline_datetime.replace("Z", "+00:00"))
    except Exception:
        return None

    if dt.date().isoformat() != day:
        return None

    return dt.hour * 60 + dt.minute


def _current_time_start_for_day(current_datetime: Optional[str], day: str) -> Optional[int]:
    """
    If day is today, return current time in minutes.
    Prevents counting already-passed time as available.
    """
    if not current_datetime:
        return None

    try:
        dt = datetime.fromisoformat(current_datetime.replace("Z", "+00:00"))
    except Exception:
        return None

    if dt.date().isoformat() != day:
        return None

    return dt.hour * 60 + dt.minute


def _extract_day_commitments(commitments: Any, day: str) -> list[Any]:
    """
    Preferred format:

    commitments = {
        "2026-06-09": [
            {"title": "School", "start": "08:00", "end": "14:00"}
        ]
    }

    Also supports flat list:

    commitments = [
        {"title": "School", "date": "2026-06-09", "start": "08:00", "end": "14:00"},
        {"title": "Tuition", "date": "2026-06-09", "start": "17:00", "end": "18:00"}
    ]
    """
    if not commitments:
        return []

    if isinstance(commitments, dict):
        return commitments.get(day, []) or []

    if isinstance(commitments, list):
        return [item for item in commitments if _get(item, "date") == day]

    return []


def _extract_day_calendar_blocks(
    calendar_blocks: list[dict[str, Any]],
    day: str,
) -> list[dict[str, Any]]:
    return [block for block in calendar_blocks or [] if block.get("date") == day]


def _item_start_end(item: Any) -> tuple[Optional[int], Optional[int]]:
    """
    Supports both:
    start/end
    start_time/end_time
    """
    start_raw = _get(item, "start") or _get(item, "start_time")
    end_raw = _get(item, "end") or _get(item, "end_time")

    return _to_minutes(start_raw), _to_minutes(end_raw)


def _build_status_payload(
    *,
    scope_feasible_on_claim: bool,
    claimed_hours_available: bool,
) -> tuple[str, Optional[str], bool, str, str]:
    """
    Returns:
    status, primary_issue, can_lock, headline, llm_next_move
    """
    if scope_feasible_on_claim and claimed_hours_available:
        return (
            "ready",
            None,
            True,
            "The study scope fits, and the student's claimed hours are available after blockers.",
            "Show the lock summary and ask the student to confirm before sending to the planner.",
        )

    if scope_feasible_on_claim and not claimed_hours_available:
        return (
            "claim_hours_unrealistic",
            "claimed_hours_not_available",
            False,
            "The study scope fits on paper, but the student's claimed hours are not actually available.",
            "Tell the student their claimed hours do not fit reality. Ask them to lower the daily hours, move commitments, or adjust scope before locking.",
        )

    if not scope_feasible_on_claim and claimed_hours_available:
        return (
            "scope_too_large",
            "scope_needs_more_time",
            False,
            "The student's claimed hours are available, but the selected study scope needs more time.",
            "Tell the student their availability is real, but the scope is too heavy. Offer to reduce scope, make a chapter revision-only, or extend within 7 days.",
        )

    return (
        "claim_and_scope_problem",
        "claimed_hours_not_available_and_scope_too_large",
        False,
        "The claimed hours are not fully available, and the selected study scope also needs more time.",
        "Tell the student both issues clearly: their claimed hours do not fit the day, and even the claimed plan is too tight. Ask them to reduce scope or change availability.",
    )


def validate_claimed_hours_guardrail(
    *,
    required_hours: float,
    user_claimed_hours_per_day: dict[str, float],
    commitments: Any = None,
    calendar_blocks: Optional[list[dict[str, Any]]] = None,
    deadline_datetime: Optional[str] = None,
    current_datetime: Optional[str] = None,
    focus_ratio: float = 0.8,
    include_debug: bool = False,
) -> dict[str, Any]:
    """
    Two-gate intake feasibility guardrail.

    This function does NOT auto-correct the student's claimed hours.
    It judges the claim as the claim.

    Gate 1: Scope-on-claim gate
        If the student's claimed hours were true, would the selected work fit?
        Formula:
            claim_based_realistic_hours = total_user_claimed_hours * focus_ratio
            scope_feasible_on_claim = claim_based_realistic_hours >= required_hours

    Gate 2: Claim reality gate
        Does the student actually have those claimed hours physically free each day
        after current time, calendar blockers, manual commitments, sleep/rest,
        and deadline cutoff?
        Formula per day:
            claim_possible_for_day = claimed_hours <= physical_free_hours

    Output is intentionally simple and LLM-facing:
        status, headline, checks, hours, issues, notes, next move.

    This is a guardrail only. It does not generate planner slots.
    """
    calendar_blocks = calendar_blocks or []
    commitments = commitments or {}
    required_hours = round(float(required_hours or 0), 2)

    daily_results: dict[str, dict[str, Any]] = {}
    day_issues: list[str] = []
    scope_issues: list[str] = []
    notes: list[str] = []

    total_user_claimed_hours = 0.0
    total_physical_free_hours = 0.0

    feasibility_logger.info(
        "[CLAIM_GUARDRAIL] start required_hours=%s focus_ratio=%s days=%s",
        required_hours,
        focus_ratio,
        list(user_claimed_hours_per_day.keys()),
    )

    for day, claimed_raw in user_claimed_hours_per_day.items():
        claimed_hours = round(float(claimed_raw or 0), 2)
        total_user_claimed_hours += claimed_hours

        window_start = 0
        window_end = 1440

        current_start = _current_time_start_for_day(current_datetime, day)
        if current_start is not None:
            window_start = max(window_start, current_start)
            notes.append(
                f"{day}: only time after {_minutes_to_time(window_start)} is counted because this is the current day."
            )

        deadline_cutoff = _deadline_cutoff_for_day(deadline_datetime, day)
        if deadline_cutoff is not None:
            old_window_end = window_end
            window_end = min(window_end, deadline_cutoff)

            if window_end < old_window_end:
                notes.append(
                    f"{day}: cutoff is {_minutes_to_time(window_end)}, so study time after that is not counted for this goal."
                )

        busy_intervals: list[tuple[int, int]] = []

        for item in _extract_day_commitments(commitments, day):
            start_m, end_m = _item_start_end(item)
            if start_m is None or end_m is None:
                continue

            for interval in _split_interval(start_m, end_m):
                clipped = _clip_interval(interval, window_start, window_end)
                if clipped:
                    busy_intervals.append(clipped)

        for block in _extract_day_calendar_blocks(calendar_blocks, day):
            start_m, end_m = _item_start_end(block)
            if start_m is None or end_m is None:
                continue

            for interval in _split_interval(start_m, end_m):
                clipped = _clip_interval(interval, window_start, window_end)
                if clipped:
                    busy_intervals.append(clipped)

        merged_busy = _merge_intervals(busy_intervals)

        busy_minutes = sum(end - start for start, end in merged_busy)
        usable_window_minutes = max(0, window_end - window_start)
        physical_free_minutes = max(0, usable_window_minutes - busy_minutes)
        physical_free_hours = round(physical_free_minutes / 60, 2)
        total_physical_free_hours += physical_free_hours

        claim_possible_for_day = claimed_hours <= physical_free_hours

        if not claim_possible_for_day:
            day_issues.append(
                f"{day}: student claimed {claimed_hours}h, but only {physical_free_hours}h is physically free after blockers/cutoff."
            )

        daily_results[day] = {
            "claimed_hours": claimed_hours,
            "physical_free_hours": physical_free_hours,
            "claim_possible": claim_possible_for_day,
            "busy_hours": round(busy_minutes / 60, 2),
            "usable_window_start": _minutes_to_time(window_start),
            "usable_window_end": _minutes_to_time(window_end),
        }

        feasibility_logger.info(
            "[CLAIM_GUARDRAIL] day=%s claimed=%.2f physical_free=%.2f claim_possible=%s busy_intervals=%s",
            day,
            claimed_hours,
            physical_free_hours,
            claim_possible_for_day,
            merged_busy,
        )

    total_user_claimed_hours = round(total_user_claimed_hours, 2)
    total_physical_free_hours = round(total_physical_free_hours, 2)

    claim_based_realistic_hours = round(total_user_claimed_hours * focus_ratio, 2)
    scope_feasible_on_claim = claim_based_realistic_hours >= required_hours

    if not scope_feasible_on_claim:
        scope_issues.append(
            f"Required {required_hours}h, but the student's claimed hours only give {claim_based_realistic_hours}h after the focus cushion."
        )

    claimed_hours_available = len(day_issues) == 0

    status, primary_issue, can_lock, headline, llm_next_move = _build_status_payload(
        scope_feasible_on_claim=scope_feasible_on_claim,
        claimed_hours_available=claimed_hours_available,
    )

    warnings = notes + day_issues + scope_issues

    result = {
        "status": status,
        "can_lock": can_lock,
        "headline": headline,
        "primary_issue": primary_issue,
        "checks": {
            "scope_fits_on_claim": scope_feasible_on_claim,
            "claimed_hours_available": claimed_hours_available,
        },
        "hours": {
            "required_hours": required_hours,
            "claimed_hours": total_user_claimed_hours,
            "claim_based_realistic_hours": claim_based_realistic_hours,
            "physical_free_hours": total_physical_free_hours,
            "focus_ratio": focus_ratio,
        },
        "day_issues": day_issues,
        "scope_issues": scope_issues,
        "notes": notes,
        "llm_next_move": llm_next_move,
        "feasible": can_lock,
        "available_hours": claim_based_realistic_hours,
        "realistic_hours": claim_based_realistic_hours,
        "warnings": warnings,
    }

    if include_debug:
        result["debug"] = {
            "daily_results": daily_results,
            "all_warnings": notes + day_issues + scope_issues,
        }

    feasibility_logger.info(
        "[CLAIM_GUARDRAIL] result status=%s can_lock=%s scope_fits_on_claim=%s claimed_hours_available=%s claimed=%.2f physical_free=%.2f claim_realistic=%.2f required=%.2f issues=%d",
        status,
        can_lock,
        scope_feasible_on_claim,
        claimed_hours_available,
        total_user_claimed_hours,
        total_physical_free_hours,
        claim_based_realistic_hours,
        required_hours,
        len(notes) + len(day_issues) + len(scope_issues),
    )

    return result


def validate_confirmed_hours(
    *,
    required_hours: float,
    daily_study_hours: dict[str, float],
    commitments: Any = None,
    calendar_blocks: Optional[list[dict[str, Any]]] = None,
    deadline_datetime: Optional[str] = None,
    current_datetime: Optional[str] = None,
    focus_ratio: float = 0.8,
    include_debug: bool = False,
) -> dict[str, Any]:
    """
    Backward-compatible wrapper for old call sites.

    daily_study_hours is treated as the student's claimed/intended hours,
    not as verified free time.
    """
    return validate_claimed_hours_guardrail(
        required_hours=required_hours,
        user_claimed_hours_per_day=daily_study_hours,
        commitments=commitments,
        calendar_blocks=calendar_blocks,
        deadline_datetime=deadline_datetime,
        current_datetime=current_datetime,
        focus_ratio=focus_ratio,
        include_debug=include_debug,
    )


__all__ = [
    "validate_claimed_hours_guardrail",
    "validate_confirmed_hours",
]