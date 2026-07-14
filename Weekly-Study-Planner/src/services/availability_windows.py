"""Deterministic availability window derivation.

The LLM may identify constraints, but raw free windows must be computed here.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional


DAY_NAME_BY_INDEX = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}


def parse_time_minutes(value: str) -> Optional[int]:
    try:
        hour, minute = value.split(":", 1)
        hour_int = int(hour)
        minute_int = int(minute)
        if not (0 <= hour_int <= 24 and 0 <= minute_int < 60):
            return None
        if hour_int == 24 and minute_int != 0:
            return None
        return hour_int * 60 + minute_int
    except Exception:
        return None


def format_minutes(value: int) -> str:
    value = max(0, min(1440, value))
    return f"{value // 60:02d}:{value % 60:02d}"


def date_range(start_date: str, end_date: str) -> Iterable[date]:
    start = datetime.fromisoformat(start_date).date()
    end = datetime.fromisoformat(end_date).date()
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def interval_segments(start: int, end: int) -> List[tuple[int, int]]:
    if start < 0 or end < 0 or start > 1440 or end > 1440:
        return []
    if start < end:
        return [(start, end)]
    if start > end:
        return [(start, 1440), (0, end)]
    return []


def subtract_interval(
    windows: List[tuple[int, int]],
    block_start: int,
    block_end: int,
) -> List[tuple[int, int]]:
    result = windows
    for segment_start, segment_end in interval_segments(block_start, block_end):
        next_windows: List[tuple[int, int]] = []
        for window_start, window_end in result:
            if segment_end <= window_start or segment_start >= window_end:
                next_windows.append((window_start, window_end))
                continue
            if segment_start > window_start:
                next_windows.append((window_start, segment_start))
            if segment_end < window_end:
                next_windows.append((segment_end, window_end))
        result = next_windows
    return result


def date_rule_applies(rule: Any, day: date) -> bool:
    if not rule:
        return True

    rule_type = getattr(rule, "type", None)
    day_text = day.isoformat()
    if rule_type == "weekly_days":
        return DAY_NAME_BY_INDEX[day.weekday()] in (getattr(rule, "days", None) or [])
    if rule_type in {"specific_dates", "one_time"}:
        return day_text in (getattr(rule, "dates", None) or [])
    if rule_type == "date_range":
        start_date = getattr(rule, "start_date", None)
        end_date = getattr(rule, "end_date", None)
        if start_date and day_text < start_date:
            return False
        if end_date and day_text > end_date:
            return False
        return True
    return True


def override_for_block(contract: Any, day_text: str, block_id: str) -> Optional[str]:
    for override in getattr(contract, "date_overrides", None) or []:
        if getattr(override, "date", None) != day_text:
            continue
        if getattr(override, "block_id", None) != block_id:
            continue
        return getattr(override, "action", None)
    return None


def calendar_event_blocks(contract: Any, day_text: str) -> List[tuple[int, int]]:
    blocks: List[tuple[int, int]] = []
    for event in getattr(contract, "calendar_events_used", None) or []:
        if getattr(event, "strictness", "hard") != "hard":
            continue
        if getattr(event, "date", None) != day_text:
            continue
        start = parse_time_minutes(getattr(event, "start_time", ""))
        end = parse_time_minutes(getattr(event, "end_time", ""))
        if start is not None and end is not None:
            blocks.append((start, end))
    return blocks


def iso_date(value: Optional[str]) -> Optional[str]:
    return value[:10] if value else None


def iso_time_minutes(value: Optional[str]) -> Optional[int]:
    if not value or len(value) < 16:
        return None
    return parse_time_minutes(value[11:16])


def fixed_commitment_blocks(contract: Any, day: date) -> List[tuple[int, int]]:
    blocks: List[tuple[int, int]] = []
    day_text = day.isoformat()
    for commitment in getattr(contract, "fixed_commitments", None) or []:
        title = getattr(commitment, "title", "")
        block_id = getattr(commitment, "id", None) or title.lower().replace(" ", "_")
        action = override_for_block(contract, day_text, block_id)
        if action == "skip":
            continue
        strictness = "soft" if action == "make_soft" else getattr(
            commitment, "strictness", "hard"
        )
        if strictness != "hard":
            continue
        if not date_rule_applies(getattr(commitment, "date_rule", None), day):
            continue
        start = parse_time_minutes(getattr(commitment, "start_time", ""))
        end = parse_time_minutes(getattr(commitment, "end_time", ""))
        if start is not None and end is not None:
            blocks.append((start, end))
    return blocks


def normalize_planning_events(goal: Any) -> List[dict]:
    """Normalize old and new dated constraints into planning-effect records."""

    events: List[dict] = []

    def append_event(event: dict) -> None:
        key = (
            event.get("type"),
            event.get("title"),
            tuple(event.get("study_scope") or []),
            event.get("strictness"),
            event.get("planning_effect"),
            event.get("date"),
            event.get("starts_at"),
            event.get("ends_at"),
        )
        for existing in events:
            existing_key = (
                existing.get("type"),
                existing.get("title"),
                tuple(existing.get("study_scope") or []),
                existing.get("strictness"),
                existing.get("planning_effect"),
                existing.get("date"),
                existing.get("starts_at"),
                existing.get("ends_at"),
            )
            if existing_key == key:
                return
        events.append(event)

    for event in getattr(goal, "planning_events", None) or []:
        event_type = getattr(event, "event_type", None)
        append_event(
            {
                "id": getattr(event, "id", None),
                "type": event_type,
                "title": getattr(event, "title", None) or str(event_type or "Event"),
                "study_scope": list(getattr(event, "study_scope", None) or []),
                "strictness": getattr(event, "strictness", "hard"),
                "planning_effect": getattr(event, "planning_effect", None),
                "date": getattr(event, "date", None),
                "starts_at": getattr(event, "starts_at", None),
                "ends_at": getattr(event, "ends_at", None),
            }
        )

    for event in getattr(goal, "deadline_events", None) or []:
        deadline_type = getattr(event, "deadline_type", "other")
        if deadline_type == "exam_like":
            event_type = "assessment"
            planning_effect = "finish_scope_before_start"
        elif deadline_type == "practice_target":
            event_type = "practice_target"
            planning_effect = "soft_completion_target"
        elif deadline_type == "casual_target":
            event_type = "casual_target"
            planning_effect = "prefer_completion_by_date"
        else:
            event_type = "other"
            planning_effect = "avoid_scheduling_during_event"
        append_event(
            {
                "id": getattr(event, "id", None),
                "type": event_type,
                "title": getattr(event, "title", None) or "Dated constraint",
                "study_scope": list(getattr(event, "study_scope", None) or []),
                "strictness": getattr(event, "strictness", "hard"),
                "planning_effect": planning_effect,
                "date": getattr(event, "date", None),
                "starts_at": getattr(event, "starts_at", None),
                "ends_at": getattr(event, "ends_at", None),
            }
        )

    deadline_datetime = getattr(goal, "deadline_datetime", None)
    deadline_type = getattr(goal, "deadline_type", "none")
    if deadline_datetime and deadline_type != "none":
        if not any(event.get("starts_at") == deadline_datetime for event in events):
            if deadline_type == "exam_like":
                event_type = "assessment"
                planning_effect = "finish_scope_before_start"
            elif deadline_type == "casual_target":
                event_type = "casual_target"
                planning_effect = "prefer_completion_by_date"
            else:
                event_type = "other"
                planning_effect = "hard_completion_deadline"
            append_event(
                {
                    "id": "normalized_goal_deadline",
                    "type": event_type,
                    "title": "Main planning cutoff",
                    "study_scope": list(getattr(goal, "subjects", None) or []),
                    "strictness": "hard",
                    "planning_effect": planning_effect,
                    "date": iso_date(deadline_datetime),
                    "starts_at": deadline_datetime,
                    "ends_at": None,
                }
            )

    return events


def planning_event_blocks(goal: Any, day_text: str) -> List[tuple[int, int]]:
    blocks: List[tuple[int, int]] = []
    for event in normalize_planning_events(goal):
        if event.get("strictness", "hard") != "hard":
            continue
        event_date = event.get("date") or iso_date(event.get("starts_at"))
        if event_date != day_text:
            continue
        effect = event.get("planning_effect")
        if effect == "unavailable_full_day":
            blocks.append((0, 1440))
            continue
        starts_at = event.get("starts_at")
        ends_at = event.get("ends_at")
        if not starts_at:
            continue
        start = iso_time_minutes(starts_at)
        if effect in {"finish_scope_before_start", "hard_completion_deadline"}:
            end = 1440
        elif effect == "avoid_scheduling_during_event":
            end = iso_time_minutes(ends_at) if ends_at else 1440
        else:
            continue
        if start is not None and end is not None:
            blocks.append((start, end))
    return blocks


def derive_raw_free_windows(goal: Any, availability: Any) -> Dict[str, dict]:
    """Return raw free windows from hard blocks.

    The output is date-keyed and matches SchedulingContract.raw_free_windows.
    """

    if not goal or not availability:
        return {}

    plan_start = getattr(goal, "plan_start", None)
    plan_end = getattr(goal, "plan_end", None)
    if not plan_start or not plan_end:
        return {}

    contract = availability.scheduling_contract
    planning_day = getattr(contract, "planning_day", None)
    day_start = parse_time_minutes(getattr(planning_day, "start_time", "07:00"))
    day_end = parse_time_minutes(getattr(planning_day, "end_time", "23:00"))
    if day_start is None or day_end is None or day_start >= day_end:
        return {}

    raw_windows: Dict[str, dict] = {}
    for day in date_range(plan_start, plan_end):
        day_text = day.isoformat()
        windows = [(day_start, day_end)]
        blocks = []
        blocks.extend(fixed_commitment_blocks(contract, day))
        blocks.extend(calendar_event_blocks(contract, day_text))
        blocks.extend(planning_event_blocks(goal, day_text))
        for block_start, block_end in blocks:
            windows = subtract_interval(windows, block_start, block_end)

        serialized = [
            {"start_time": format_minutes(start), "end_time": format_minutes(end)}
            for start, end in windows
            if end > start
        ]
        raw_windows[day_text] = {
            "day_label": DAY_NAME_BY_INDEX[day.weekday()],
            "windows": serialized,
            "free_minutes": sum(end - start for start, end in windows if end > start),
        }

    return raw_windows


def raw_free_windows_match(expected: Dict[str, dict], actual: Dict[str, Any]) -> bool:
    actual_plain = {
        date_text: {
            "day_label": getattr(day, "day_label", None),
            "windows": [
                {
                    "start_time": window.start_time,
                    "end_time": window.end_time,
                }
                for window in day.windows
            ],
            "free_minutes": day.free_minutes,
        }
        for date_text, day in (actual or {}).items()
    }
    return expected == actual_plain
