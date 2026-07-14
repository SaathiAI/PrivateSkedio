"""Validation and deterministic runtime enrichment for Intake contracts.

This module is the hard boundary between the Intake LLM and everything
downstream.

Mental model:
- the Intake model may draft a contract
- this service decides whether that contract is acceptable
- if acceptable, this service also derives runtime-only planning context such as
  calendar blockers and legal available time windows

Anything here should be treated as code-owned truth, not model opinion.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date as _date
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import ValidationError

from src.models.intake import IntakeAgentOutput
from src.services.intake_feasibility import validate_confirmed_hours
IntakeValidationCode = Literal[
    "ok",
    "invalid_intake_contract",
    "ready_contract_incomplete",
    "hard_commitment_overlap",
    "invalid_date_window",
    "missing_rest_window",
    "past_date_window",
    "window_too_long",
    "calendar_unavailable",
    "feasibility_feedback",
    "feasibility_failed",
]


@dataclass
class IntakeValidationResult:
    """Structured validator result returned back into the Intake worker loop.

    The worker uses this as the deterministic observation for commit_intake:
    accepted/rejected, reason code, optional enriched intake, and student-safe
    summary text.
    """

    accepted: bool
    code: IntakeValidationCode
    intake: Optional[IntakeAgentOutput] = None
    feasibility: Optional[dict[str, Any]] = None
    details: Optional[dict[str, Any]] = None
    student_safe_summary: str = ""

    def tool_payload(self) -> dict[str, Any]:
        return {
            "ok": self.code == "ok",
            "code": self.code,
            "reason": self.student_safe_summary or self.code,
        }


def _parse_hhmm_to_minutes(value: str) -> Optional[int]:
    """Convert an HH:MM string to minutes after midnight."""

    try:
        hour, minute = value.split(":", 1)
        return int(hour) * 60 + int(minute)
    except Exception:
        return None


def _format_minutes_as_hhmm(value: int) -> str:
    """Convert minutes after midnight to an HH:MM string."""

    value = max(0, min(1439, int(value)))
    return f"{value // 60:02d}:{value % 60:02d}"


def _build_inclusive_date_range(start_date: str, end_date: str) -> list[str]:
    """Return every ISO date from start_date through end_date, inclusive."""

    start = _date.fromisoformat(start_date)
    end = _date.fromisoformat(end_date)
    days = []
    cursor = start
    while cursor <= end:
        days.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return days


def _get_current_day_start_minute(
    current_datetime: Optional[str],
    day: str,
) -> Optional[int]:
    """Return the current clock minute when the requested day is today."""

    if not current_datetime:
        return None
    try:
        parsed = datetime.fromisoformat(current_datetime.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.date().isoformat() != day:
        return None
    return min(1439, parsed.hour * 60 + parsed.minute)


def _parse_current_date(current_datetime: Optional[str]) -> Optional[_date]:
    """Extract the local date from the runtime current_datetime value."""

    if not current_datetime:
        return None
    try:
        return datetime.fromisoformat(current_datetime.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _get_deadline_cutoff_minute(deadline_datetime: Optional[str], day: str) -> Optional[int]:
    """Return the deadline cutoff minute when the deadline falls on day."""

    if not deadline_datetime:
        return None
    try:
        parsed = datetime.fromisoformat(deadline_datetime.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.date().isoformat() != day:
        return None
    return min(1439, parsed.hour * 60 + parsed.minute)


def _clip_interval_to_window(
    interval: tuple[int, int],
    window_start: int,
    window_end: int,
) -> Optional[tuple[int, int]]:
    """Clip an interval so only the portion inside the day window remains."""

    start = max(interval[0], window_start)
    end = min(interval[1], window_end)
    if end <= start:
        return None
    return start, end


def _split_local_block_by_date(
    *,
    date: str,
    start: str,
    end: str,
) -> list[tuple[str, int, int]]:
    """Split a same-day or overnight local blocker into date-keyed intervals."""

    start_m = _parse_hhmm_to_minutes(start)
    end_m = _parse_hhmm_to_minutes(end)
    if start_m is None or end_m is None or start_m == end_m:
        return []
    if end_m > start_m:
        return [(date, start_m, end_m)]

    try:
        next_day = (_date.fromisoformat(date) + timedelta(days=1)).isoformat()
    except ValueError:
        return []
    return [(date, start_m, 1440), (next_day, 0, end_m)]


def _merge_overlapping_intervals(
    intervals: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Merge overlapping or touching intervals into canonical busy blocks."""

    if not intervals:
        return []
    merged: list[tuple[int, int]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
            continue
        merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def _normalize_calendar_blockers(calendar_blocks: Any) -> list[dict[str, Any]]:
    """Normalize supported calendar block shapes into one internal schema."""

    if isinstance(calendar_blocks, dict):
        raw_blocks = (
            calendar_blocks.get("blocked_slots")
            or calendar_blocks.get("UNAVAILABLE_BUSY_TIME")
            or []
        )
    else:
        raw_blocks = calendar_blocks or []

    normalized = []
    for block in raw_blocks:
        if not isinstance(block, dict):
            continue
        date = block.get("date")
        start = block.get("start") or block.get("start_time")
        end = block.get("end") or block.get("end_time")
        if not date or not start or not end:
            continue
        normalized.append(
            {
                "date": str(date),
                "title": block.get("title") or "Calendar blocker",
                "start": str(start),
                "end": str(end),
                "source": block.get("source") or "google_calendar",
            }
        )
    return normalized


def _build_available_time_windows(
    *,
    start_date: str,
    end_date: str,
    time_blocks: Any,
    calendar_blocks: Any,
    deadline_datetime: Optional[str],
    current_datetime: Optional[str],
) -> dict[str, list[dict[str, str]]]:
    """Return date-keyed free intervals after commitments, calendar, now, and deadline.

    The returned windows are runtime state, not part of the LLM-facing Intake
    contract. Past dates return empty windows, today starts at the current time,
    and future dates are clipped only by commitments, calendar blockers, and
    deadline.
    """

    days = _build_inclusive_date_range(start_date, end_date)
    day_set = set(days)
    busy_by_day: dict[str, list[tuple[int, int]]] = {day: [] for day in days}

    # Convert manual time blocks into one date-keyed busy interval collection.
    if isinstance(time_blocks, dict):
        commitment_items = []
        for day, items in time_blocks.items():
            for item in items or []:
                commitment_items.append((day, item))
    elif isinstance(time_blocks, list):
        commitment_items = [(item.get("date"), item) for item in time_blocks if isinstance(item, dict)]
    else:
        commitment_items = []

    for day, item in commitment_items:
        if not day:
            continue
        start = getattr(item, "start", None) if not isinstance(item, dict) else item.get("start")
        end = getattr(item, "end", None) if not isinstance(item, dict) else item.get("end")
        if not start or not end:
            continue
        for block_day, block_start, block_end in _split_local_block_by_date(
            date=str(day),
            start=str(start),
            end=str(end),
        ):
            if block_day in day_set:
                busy_by_day[block_day].append((block_start, block_end))

    # Calendar blockers use start_time/end_time in some tools and start/end in others.
    for block in _normalize_calendar_blockers(calendar_blocks):
        for block_day, block_start, block_end in _split_local_block_by_date(
            date=block["date"],
            start=block["start"],
            end=block["end"],
        ):
            if block_day in day_set:
                busy_by_day[block_day].append((block_start, block_end))

    windows: dict[str, list[dict[str, str]]] = {}
    today = _parse_current_date(current_datetime)
    for day in days:
        day_date = _date.fromisoformat(day)
        if today is not None and day_date < today:
            windows[day] = []
            continue

        window_start = 0
        window_end = 1439

        current_start = _get_current_day_start_minute(current_datetime, day)
        if current_start is not None:
            window_start = max(window_start, current_start)

        deadline_cutoff = _get_deadline_cutoff_minute(deadline_datetime, day)
        if deadline_cutoff is not None:
            window_end = min(window_end, deadline_cutoff)

        if window_end <= window_start:
            windows[day] = []
            continue

        clipped_busy = []
        for interval in busy_by_day[day]:
            clipped = _clip_interval_to_window(interval, window_start, window_end)
            if clipped:
                clipped_busy.append(clipped)

        merged_busy = _merge_overlapping_intervals(clipped_busy)
        free_intervals = []
        cursor = window_start
        for busy_start, busy_end in merged_busy:
            if busy_start > cursor:
                free_intervals.append((cursor, busy_start))
            cursor = max(cursor, busy_end)
        if cursor < window_end:
            free_intervals.append((cursor, window_end))

        windows[day] = [
            {
                "start": _format_minutes_as_hhmm(start),
                "end": _format_minutes_as_hhmm(end),
            }
            for start, end in free_intervals
            if end > start
        ]

    return windows


def _build_scheduling_context(
    *,
    intake: IntakeAgentOutput,
    calendar_blocks: Any,
    available_time_windows: dict[str, list[dict[str, str]]],
) -> dict[str, Any]:
    """Build the canonical runtime scheduling context for planner handoff.

    This is the bridge object passed from validated intake into planner. It is
    intentionally planner-facing and should contain resolved runtime context,
    not just raw user utterances.
    """

    availability = intake.availability
    return {
        "timezone": availability.timezone if availability else "local",
        "daily_study_hours": dict(availability.daily_study_hours)
        if availability
        else {},
        "time_blocks": availability.model_dump().get("time_blocks", {})
        if availability
        else {},
        "calendar_blocks": calendar_blocks or [],
        "available_time_windows": available_time_windows,
    }


def _normalize_intake_payload(intake_payload: dict[str, Any]) -> dict[str, Any]:
    """Repair common mechanical schema slips before strict validation.

    This is not business logic.
    It only removes wrapper junk and repairs harmless LLM/null shape mistakes.
    """

    if not isinstance(intake_payload, dict):
        return {}

    payload = dict(intake_payload)

    # Sometimes tool wrappers / model output leak these into the contract.
    # They are not part of IntakeAgentOutput.
    payload.pop("config", None)
    payload.pop("kwargs", None)
    payload.pop("metadata", None)
    payload.pop("internal_notes", None)

    # If somehow the whole tool args object reaches here, unwrap it.
    if "intake_data" in payload and isinstance(payload["intake_data"], dict):
        payload = dict(payload["intake_data"])
        payload.pop("config", None)
        payload.pop("kwargs", None)
        payload.pop("metadata", None)

    # Top-level list fields should never be null.
    if payload.get("study_items") is None:
        payload["study_items"] = []

    # Goal inner lists should never be null.
    goal = payload.get("goal")
    if isinstance(goal, dict):
        goal = dict(goal)
        if goal.get("subjects") is None:
            goal["subjects"] = []
        if goal.get("study_scope") is None:
            goal["study_scope"] = []
        payload["goal"] = goal

    # Availability can be null while pending.
    availability = payload.get("availability")
    if not isinstance(availability, dict):
        return payload

    availability = dict(availability)
    payload["availability"] = availability

    # Remove wrapper junk if model put it inside availability.
    availability.pop("config", None)
    availability.pop("kwargs", None)
    availability.pop("metadata", None)

    # Repair common nulls.
    if availability.get("daily_study_hours") is None:
        availability["daily_study_hours"] = {}

    if availability.get("time_blocks") is None:
        availability["time_blocks"] = {}

    if availability.get("planning_notes") is None:
        availability["planning_notes"] = []

    # Repair common mistake: study_items accidentally nested under availability.
    if "study_items" in availability:
        misplaced_value = availability.pop("study_items")
        current_value = payload.get("study_items")
        if current_value in (None, []):
            payload["study_items"] = misplaced_value or []

    # Remove accidental non-schema field.
    availability.pop("next", None)

    return payload


def _find_invalid_commitment_times(intake: IntakeAgentOutput) -> list[str]:
    """Return validation issues for malformed manual commitment time ranges."""

    availability = intake.availability
    if not availability:
        return []

    issues: list[str] = []
    for day, time_blocks in availability.time_blocks.items():
        for commitment in time_blocks:
            if not commitment.start or not commitment.end:
                continue
            block_start = _parse_hhmm_to_minutes(commitment.start)
            block_end = _parse_hhmm_to_minutes(commitment.end)
            if block_start is None or block_end is None:
                issues.append(
                    f"Hard commitment '{commitment.title}' on {day} has invalid time "
                    f"range {commitment.start}-{commitment.end}."
                )
    return issues


def _find_ready_contract_issues(intake: IntakeAgentOutput) -> list[str]:
    """Return missing fields that prevent a ready contract from being locked."""

    issues: list[str] = []
    if not intake.goal:
        issues.append("goal is required before lock")
    elif not intake.goal.start_date or not intake.goal.end_date:
        issues.append("goal.start_date and goal.end_date are required before lock")

    if not intake.study_items:
        issues.append("at least one study_item is required before lock")

    if not intake.availability:
        issues.append("availability is required before lock")
    elif not intake.availability.daily_study_hours:
        issues.append("availability.daily_study_hours is required before lock")

    return issues


def _find_missing_rest_window_dates(intake: IntakeAgentOutput) -> list[str]:
    """Return plan dates that lack a user-declared protected rest window."""

    if not intake.goal or not intake.availability:
        return []
    if not intake.goal.start_date or not intake.goal.end_date:
        return []

    try:
        days = _build_inclusive_date_range(
            intake.goal.start_date,
            intake.goal.end_date,
        )
    except ValueError:
        return []

    missing: list[str] = []
    time_blocks_by_day = intake.availability.time_blocks or {}
    for day in days:
        commitments = time_blocks_by_day.get(day) or []
        has_rest_window = any(
            getattr(commitment, "source", None) == "user_rest_window"
            for commitment in commitments
        )
        if not has_rest_window:
            missing.append(day)
    return missing


def _resolve_student_current_datetime(intake: IntakeAgentOutput) -> str:
    """Return the current datetime in the student's declared timezone."""

    now_utc = datetime.now(timezone.utc)
    timezone_name = intake.availability.timezone if intake.availability else None
    if not timezone_name:
        return now_utc.isoformat()

    try:
        return now_utc.astimezone(ZoneInfo(timezone_name)).isoformat()
    except (ZoneInfoNotFoundError, Exception):
        return now_utc.isoformat()


def _resolve_student_today(
    *,
    intake: IntakeAgentOutput,
    runtime_state: dict[str, Any],
) -> _date:
    """Return today's date using runtime override first, then student timezone."""

    current_datetime = runtime_state.get("current_datetime")
    if isinstance(current_datetime, str) and current_datetime.strip():
        try:
            return datetime.fromisoformat(
                current_datetime.strip().replace("Z", "+00:00")
            ).date()
        except ValueError:
            pass

    return datetime.fromisoformat(_resolve_student_current_datetime(intake)).date()


def _find_past_ready_date_issues(
    *,
    intake: IntakeAgentOutput,
    today: _date,
) -> list[str]:
    """Return ready-contract issues caused by dates before today."""

    issues: list[str] = []
    goal = intake.goal
    availability = intake.availability
    if not goal:
        return issues

    try:
        start = _date.fromisoformat(goal.start_date or "")
        end = _date.fromisoformat(goal.end_date or "")
    except ValueError:
        return issues

    if start < today:
        issues.append(f"goal.start_date {start.isoformat()} is before today {today.isoformat()}")
    if end < today:
        issues.append(f"goal.end_date {end.isoformat()} is before today {today.isoformat()}")

    if availability:
        for day in availability.daily_study_hours:
            try:
                day_date = _date.fromisoformat(day)
            except ValueError:
                continue
            if day_date < today:
                issues.append(
                    "availability.daily_study_hours contains past date "
                    f"{day_date.isoformat()} before today {today.isoformat()}"
                )

        for day, commitments in availability.time_blocks.items():
            try:
                day_date = _date.fromisoformat(day)
            except ValueError:
                continue
            if day_date < today:
                allows_overnight_spill = False
                for commitment in commitments or []:
                    start = getattr(commitment, "start", None)
                    end = getattr(commitment, "end", None)
                    start_m = _parse_hhmm_to_minutes(start) if start else None
                    end_m = _parse_hhmm_to_minutes(end) if end else None
                    if (
                        start_m is not None
                        and end_m is not None
                        and end_m <= start_m
                        and day_date + timedelta(days=1) >= today
                    ):
                        allows_overnight_spill = True
                        break
                if allows_overnight_spill:
                    continue
                issues.append(
                    "availability.time_blocks contains past date "
                    f"{day_date.isoformat()} before today {today.isoformat()}"
                )

    return issues


def _load_calendar_blocks(
    *,
    start_date: str,
    end_date: str,
    user_id: Optional[str],
    runtime_state: dict[str, Any],
    logger: logging.Logger,
) -> tuple[Optional[list[dict[str, Any]]], Optional[str]]:
    """Load calendar blockers for the requested date window."""

    try:
        from src.tools.calendar_ops import get_non_skedioai_events_core

        cal_raw = get_non_skedioai_events_core(start_date, end_date, user_id=user_id)
        cal_data = json.loads(cal_raw)
        blocks = cal_data.get("blocked_slots", [])
        runtime_state["calendar_blocks"] = blocks
        logger.info(
            "[VALIDATOR] calendar_fetch source=api blocks=%d window=%s..%s",
            len(blocks),
            start_date,
            end_date,
        )
        return blocks, None
    except Exception as exc:
        logger.warning("[VALIDATOR] calendar_fetch source=api error=%s", exc)
        runtime_state["calendar_blocks"] = None
        return None, str(exc)


def validate_intake_contract(
    *,
    intake_payload: dict[str, Any],
    user_id: Optional[str],
    runtime_state: dict[str, Any],
    logger: logging.Logger,
) -> IntakeValidationResult:
    """Validate one committed intake contract and return one standard result.

    This is the single authoritative gate for Intake state:
    - schema validation
    - lock-readiness checks
    - date-window and past-date checks
    - calendar loading
    - runtime available-window derivation
    - feasibility checks

    If Intake is the "conversation brain", this function is the "contract judge".
    """

    normalized_payload = _normalize_intake_payload(intake_payload)

    try:
        intake = IntakeAgentOutput.model_validate(normalized_payload)
    except ValidationError as exc:
        logger.warning(
            "[VALIDATOR] gate=pydantic_validation rejected=true errors=%s",
            exc.errors(),
        )
        return IntakeValidationResult(
            accepted=False,
            code="invalid_intake_contract",
            details={"errors": exc.errors()},
            student_safe_summary=(
                "The intake contract did not match the required schema. "
                "Repair the JSON and ask only the next useful question."
            ),
        )

    intake_is_ready = intake.status == "approved"

    if intake_is_ready:
        ready_issues = _find_ready_contract_issues(intake)
        if ready_issues:
            logger.warning(
                "[VALIDATOR] gate=ready_contract rejected=true issues=%s",
                ready_issues,
            )
            return IntakeValidationResult(
                accepted=False,
                code="ready_contract_incomplete",
                intake=intake,
                details={"issues": ready_issues},
                student_safe_summary=(
                    "The contract is marked ready, but it is missing required "
                    "lock details. Ask the student for the missing piece before "
                    "sending anything to the planner."
                ),
            )

        hard_commitment_issues = _find_invalid_commitment_times(intake)
        logger.info(
            "[VALIDATOR] gate=hard_commitment_overlap checked=%s issues=%d",
            list(intake.availability.time_blocks.keys())
            if intake.availability
            else [],
            len(hard_commitment_issues),
        )
        if hard_commitment_issues:
            logger.warning(
                "[VALIDATOR] gate=hard_commitment_overlap rejected=true issues=%s",
                hard_commitment_issues,
            )
            return IntakeValidationResult(
                accepted=False,
                code="hard_commitment_overlap",
                intake=intake,
                details={"issues": hard_commitment_issues},
                student_safe_summary=(
                    "Some commitment times are invalid. Ask the student to clarify "
                    "the affected commitment before locking."
                ),
            )

        missing_rest_window_dates = _find_missing_rest_window_dates(intake)
        logger.info(
            "[VALIDATOR] gate=rest_window checked=true missing_dates=%s",
            missing_rest_window_dates,
        )
        if missing_rest_window_dates:
            logger.warning(
                "[VALIDATOR] gate=rest_window rejected=true missing_dates=%s",
                missing_rest_window_dates,
            )
            return IntakeValidationResult(
                accepted=False,
                code="missing_rest_window",
                intake=intake,
                details={"missing_dates": missing_rest_window_dates},
                student_safe_summary=(
                    "The contract is marked ready, but protected sleep/rest "
                    "windows are missing for some plan dates. Ask when the "
                    "student sleeps/wakes or whether to use their stated rest "
                    "window for every missing date before locking."
                ),
            )

    feasibility = None

    if intake.goal and intake.goal.start_date and intake.goal.end_date:
        start_date = intake.goal.start_date
        end_date = intake.goal.end_date

        try:
            start_day = _date.fromisoformat(start_date)
            end_day = _date.fromisoformat(end_date)
            window_days = (end_day - start_day).days + 1
        except ValueError as exc:
            return IntakeValidationResult(
                accepted=False,
                code="invalid_date_window",
                intake=intake,
                details={"error": str(exc)},
                student_safe_summary=(
                    "The date window is invalid. Ask for dates in YYYY-MM-DD format."
                ),
            )

        if window_days < 1:
            logger.warning(
                "[VALIDATOR] gate=date_window_order rejected=true start=%s end=%s",
                start_date,
                end_date,
            )
            return IntakeValidationResult(
                accepted=False,
                code="invalid_date_window",
                intake=intake,
                details={"start_date": start_date, "end_date": end_date},
                student_safe_summary=(
                    "The plan end date is before the start date. Ask the student "
                    "to confirm the correct study window."
                ),
            )

        if window_days > 7:
            logger.warning(
                "[VALIDATOR] gate=window_cap rejected=true window_days=%s cap=7",
                window_days,
            )
            return IntakeValidationResult(
                accepted=False,
                code="window_too_long",
                intake=intake,
                details={"window_days": window_days, "cap_days": 7},
                student_safe_summary=(
                    f"The plan window is {window_days} days, but intake plans are "
                    "capped at 7 days. Help the student choose a shorter window."
                ),
            )

        if intake_is_ready:
            today = _resolve_student_today(intake=intake, runtime_state=runtime_state)
            past_date_issues = _find_past_ready_date_issues(intake=intake, today=today)
            if past_date_issues:
                current_datetime = (
                    runtime_state.get("current_datetime")
                    if isinstance(runtime_state.get("current_datetime"), str)
                    else None
                ) or _resolve_student_current_datetime(intake)
                runtime_state["available_time_windows"] = _build_available_time_windows(
                    start_date=start_date,
                    end_date=end_date,
                    time_blocks=intake.availability.time_blocks if intake.availability else {},
                    calendar_blocks=runtime_state.get("calendar_blocks") or [],
                    deadline_datetime=intake.goal.deadline_datetime if intake.goal else None,
                    current_datetime=current_datetime,
                )
                runtime_state["scheduling_context"] = _build_scheduling_context(
                    intake=intake,
                    calendar_blocks=runtime_state.get("calendar_blocks") or [],
                    available_time_windows=runtime_state["available_time_windows"],
                )
                logger.warning(
                    "[VALIDATOR] gate=past_date_window rejected=true today=%s issues=%s",
                    today.isoformat(),
                    past_date_issues,
                )
                return IntakeValidationResult(
                    accepted=False,
                    code="past_date_window",
                    intake=intake,
                    details={"today": today.isoformat(), "issues": past_date_issues},
                    student_safe_summary=(
                        "This contract includes dates that are already in the past. "
                        "Update the study window and date-wise hours before locking."
                    ),
                )

        calendar_blocks, calendar_error = _load_calendar_blocks(
            start_date=start_date,
            end_date=end_date,
            user_id=user_id,
            runtime_state=runtime_state,
            logger=logger,
        )

        current_datetime = (
            runtime_state.get("current_datetime")
            if isinstance(runtime_state.get("current_datetime"), str)
            else None
        ) or _resolve_student_current_datetime(intake)
        runtime_state["available_time_windows"] = _build_available_time_windows(
            start_date=start_date,
            end_date=end_date,
            time_blocks=intake.availability.time_blocks if intake.availability else {},
            calendar_blocks=calendar_blocks or [],
            deadline_datetime=intake.goal.deadline_datetime if intake.goal else None,
            current_datetime=current_datetime,
        )
        runtime_state["scheduling_context"] = _build_scheduling_context(
            intake=intake,
            calendar_blocks=calendar_blocks or [],
            available_time_windows=runtime_state["available_time_windows"],
        )
        logger.info(
            "[VALIDATOR] scheduling_context updated available_days=%s",
            list(runtime_state["available_time_windows"].keys()),
        )

        if calendar_error:
            logger.info(
                "[VALIDATOR] gate=calendar_optional warning=true ready=%s error=%s",
                intake_is_ready,
                calendar_error,
            )
            runtime_state["calendar_warning"] = calendar_error

        if (
            intake.study_items
            and intake.availability
            and intake.availability.daily_study_hours
        ):
            required_hours = round(
                sum(float(item.estimated_hours or 0) for item in intake.study_items),
                2,
            )
            logger.info(
                "[VALIDATOR] feasibility_triggered=true required_h=%.1f items=%d days=%s",
                required_hours,
                len(intake.study_items),
                list(intake.availability.daily_study_hours.keys()),
            )

            feasibility = validate_confirmed_hours(
                required_hours=required_hours,
                daily_study_hours=dict(intake.availability.daily_study_hours),
                commitments=intake.availability.time_blocks or {},
                calendar_blocks=calendar_blocks or [],
                deadline_datetime=intake.goal.deadline_datetime if intake.goal else None,
                current_datetime=current_datetime,
                focus_ratio=0.8,
            )

            runtime_state["feasibility_result"] = feasibility
            logger.info(
                "[VALIDATOR] gate=feasibility required_h=%.1f realistic_h=%.1f feasible=%s",
                required_hours,
                feasibility["realistic_hours"],
                feasibility["feasible"],
            )
            safe_hours = round(float(feasibility.get("realistic_hours", 0)), 2)
            primary_issue = feasibility.get("primary_issue")
            
            if primary_issue == "claimed_hours_not_available":
                reason = (
                    (feasibility.get("day_issues") or [
                        "availability.daily_study_hours claims more time than is physically available"
                    ])[0]
                )
            elif required_hours > safe_hours:
                reason = (
                    f"study_items require {required_hours}h but safe capacity is {safe_hours}h"
                )
            else:
                reason = feasibility.get("headline", "feasibility check failed")

            if not feasibility["feasible"]:
                logger.warning(
                    "[VALIDATOR] gate=feasibility rejected=true required_h=%.1f realistic_h=%.1f warnings=%s",
                    required_hours,
                    feasibility["realistic_hours"],
                    feasibility["warnings"],
                )
                if not intake_is_ready:
                    return IntakeValidationResult(
                        accepted=True,
                        code="feasibility_feedback",
                        intake=intake,
                        feasibility=feasibility,
                        student_safe_summary=(
                            reason
                        ),
                    )

                return IntakeValidationResult(
                    accepted=False,
                    code="feasibility_failed",
                    intake=intake,
                    feasibility=feasibility,
                    student_safe_summary=reason
                )
        else:
            skip_reason = (
                "no_study_items"
                if not intake.study_items
                else "no_confirmed_hours"
            )
            logger.info(
                "[VALIDATOR] feasibility_triggered=false reason=%s",
                skip_reason,
            )

    logger.info(
        "[VALIDATOR] commit_intake accepted=true status=%s intake_ready=%s",
        intake.status,
        intake_is_ready,
    )
    return IntakeValidationResult(
        accepted=True,
        code="ok",
        intake=intake,
        feasibility=feasibility,
        student_safe_summary="Intake contract accepted.",
    )


__all__ = [
    "IntakeValidationCode",
    "IntakeValidationResult",
    "_build_available_time_windows",
    "validate_intake_contract",
]
