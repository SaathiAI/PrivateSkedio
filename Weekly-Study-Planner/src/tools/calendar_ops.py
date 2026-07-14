import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GOOGLE_CONFIG_DIR = PROJECT_ROOT / "src" / "config" / "google"

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CREDENTIALS_PATH = str(GOOGLE_CONFIG_DIR / "credentials.json")
TOKEN_PATH = str(GOOGLE_CONFIG_DIR / "create_events.json")

ALERT_EMAIL             = os.getenv("SAATHI_ALERT_EMAIL", "")
GMAIL_USER              = os.getenv("GMAIL_USER")
GMAIL_PASSWORD          = os.getenv("GMAIL_APP_PASSWORD")
MISSED_THRESHOLD_MINUTES = 30





def _local_calendar_fallback_allowed() -> bool:
    """
    Local create_events.json is a dev convenience, not production auth.
    Production should require a connected per-user Google Calendar.
    """
    explicit = os.getenv("SAATHI_ALLOW_LOCAL_CALENDAR_FALLBACK")
    return explicit is not None and explicit.lower() in {"1", "true", "yes", "on"}


def get_service():
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise Exception(f"Token missing at {TOKEN_PATH}")
        with open(TOKEN_PATH, "w") as token:
            token.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)

def get_service_for_user_or_default(user_id: str = None):
    """
    Prefer the user's OAuth calendar tokens from Supabase.
    Fall back to the local create_events.json token only in dev/test.
    """
    oauth_error = None
    if user_id:
        try:
            from src.api.calendar_service import get_calendar_service_for_user

            return get_calendar_service_for_user(user_id)
        except Exception as e:
            oauth_error = e

    if _local_calendar_fallback_allowed():
        return get_service(), "primary"

    if user_id:
        raise Exception(
            "Google Calendar is not connected for this user. "
            "Ask the user to connect calendar via /auth/calendar/connect."
        ) from oauth_error

    raise Exception(
        "No user_id was provided for calendar access, and local calendar fallback is disabled."
    )

def _ensure_utc(iso: str) -> str:
    if not iso.endswith("Z") and "+" not in iso:
        return iso + "Z"
    return iso

def create_event_core(summary: str, description: str, start_iso: str, end_iso: str, event_id: str = None, user_id: str = None) -> str:
    service, calendar_id = get_service_for_user_or_default(user_id)
    if "+05:30" not in start_iso and "Z" not in start_iso: start_iso += "+05:30"
    if "+05:30" not in end_iso and "Z" not in end_iso: end_iso += "+05:30"
    
    event = service.events().insert(calendarId=calendar_id, body={
        "summary": summary, "description": description,
        "start": {"dateTime": start_iso, "timeZone": "Asia/Kolkata"},
        "end": {"dateTime": end_iso, "timeZone": "Asia/Kolkata"},
        "extendedProperties": {"private": {"source": "skedioai", "event_id": event_id or "", "is_completed": "false"}}
    }).execute()
    return f"Created: '{event['summary']}'"




def _tasks_from_plan(plan: dict) -> list[dict]:
    """
    Accept both the old flat task plan and the V2 Day -> Session plan.
    Calendar events stay session-level; content/checklist items live in the description.
    """
    if plan.get("tasks"):
        return plan.get("tasks") or []

    tasks = []
    for day in plan.get("days") or []:
        date = day.get("date")
        for session in day.get("sessions") or []:
            if not date or not session.get("start_time") or not session.get("end_time"):
                continue

            content_lines = []
            for content in session.get("contents") or []:
                name = content.get("name") or content.get("canonical_name") or content.get("match_key")
                if name:
                    content_lines.append(f"- {name}")

            allocation_lines = []
            for allocation in session.get("allocated_hours") or []:
                subject = allocation.get("subject") or "General"
                chapter = allocation.get("chapter") or "Study"
                hours = allocation.get("hours") or 0
                allocation_lines.append(f"- {subject} / {chapter}: {hours}h")

            description_parts = [
                f"SkedioAI session_id: {session.get('session_id', '')}",
                f"Type: {session.get('session_type', 'study')}",
            ]
            if allocation_lines:
                description_parts.append("Allocations:\n" + "\n".join(allocation_lines))
            if content_lines:
                description_parts.append("Checklist:\n" + "\n".join(content_lines))

            tasks.append(
                {
                    "date": date,
                    "start_time": session.get("start_time"),
                    "end_time": session.get("end_time"),
                    "title": session.get("title") or "SkedioAI Study Session",
                    "description": "\n\n".join(description_parts),
                    "event_id": session.get("session_id"),
                }
            )

    return tasks


def create_events_from_plan_core(plan_json: str, user_id: str = None) -> str:
    service, calendar_id = get_service_for_user_or_default(user_id)
    try:
        plan = json.loads(plan_json) if isinstance(plan_json, str) else plan_json
    except Exception:
        return "Invalid JSON"

    tasks = _tasks_from_plan(plan)
    if not tasks:
        return "No schedulable sessions found"

    created = []
    failed = 0
    for task in tasks:
        try:
            start_dt = datetime.strptime(f"{task['date']} {task['start_time']}", "%Y-%m-%d %H:%M")
            end_dt = datetime.strptime(f"{task['date']} {task['end_time']}", "%Y-%m-%d %H:%M")
            if end_dt < start_dt:
                end_dt += timedelta(days=1)

            service.events().insert(calendarId=calendar_id, body={
                "summary": task["title"],
                "description": task.get("description") or task.get("event_id", ""),
                "start": {"dateTime": start_dt.isoformat(), "timeZone": "Asia/Kolkata"},
                "end": {"dateTime": end_dt.isoformat(), "timeZone": "Asia/Kolkata"},
                "extendedProperties": {
                    "private": {
                        "source": "skedioai",
                        "plan_id": plan.get("plan_id", ""),
                        "event_id": task.get("event_id", ""),
                        "is_completed": "false",
                    }
                },
            }).execute()
            created.append(task["title"])
        except Exception:
            failed += 1

    return f"Created {len(created)}/{len(tasks)} calendar events; failed {failed}"


def list_events_core(time_min_iso: str, time_max_iso: str, max_results: int = 10, user_id: str = None) -> str:
    service, calendar_id = get_service_for_user_or_default(user_id)
    result = service.events().list(
        calendarId=calendar_id, timeMin=_ensure_utc(time_min_iso), timeMax=_ensure_utc(time_max_iso),
        maxResults=max_results, singleEvents=True, orderBy="startTime"
    ).execute()
    events = result.get("items", [])
    if not events: return "No events"
    return "\n".join([f"- {e['summary']}" for e in events])

def delete_skedioai_events_in_range_core(time_min_iso: str, time_max_iso: str, user_id: str = None) -> str:
    service, calendar_id = get_service_for_user_or_default(user_id)
    result = service.events().list(
        calendarId=calendar_id, timeMin=_ensure_utc(time_min_iso), timeMax=_ensure_utc(time_max_iso),
        singleEvents=True
    ).execute()
    deleted = 0
    for e in result.get("items", []):
        if e.get("extendedProperties", {}).get("private", {}).get("source") == "skedioai":
            is_completed = e.get("extendedProperties", {}).get("private", {}).get("is_completed", "false")
            if is_completed == "true":
                continue
            service.events().delete(calendarId=calendar_id, eventId=e["id"]).execute()
            deleted += 1
    return f"Deleted {deleted} events"

def delete_skedioai_event_by_slot_core(date: str, start_time: str, end_time: str, user_id: str = None) -> str:
    service, calendar_id = get_service_for_user_or_default(user_id)
    start_dt = datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M")
    end_dt = datetime.strptime(f"{date} {end_time}", "%Y-%m-%d %H:%M")
    if end_dt <= start_dt: end_dt += timedelta(days=1)
    
    result = service.events().list(
        calendarId=calendar_id,
        timeMin=start_dt.strftime("%Y-%m-%dT%H:%M:00+05:30"),
        timeMax=end_dt.strftime("%Y-%m-%dT%H:%M:00+05:30"),
        singleEvents=True
    ).execute()
    
    for e in result.get("items", []):
        if e.get("extendedProperties", {}).get("private", {}).get("source") == "skedioai":
            service.events().delete(calendarId=calendar_id, eventId=e["id"]).execute()
            return f"Deleted: {e['summary']}"
    return "Not found"

def mark_event_completed_core(date: str, start_time: str, end_time: str, completed: bool = True,match_key: str = None, user_id: str = None) -> str:
    service, calendar_id = get_service_for_user_or_default(user_id)
    start_dt = datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M")
    end_dt = datetime.strptime(f"{date} {end_time}", "%Y-%m-%d %H:%M")
    if end_dt <= start_dt: end_dt += timedelta(days=1)
    
    result = service.events().list(
        calendarId=calendar_id,
        timeMin=start_dt.strftime("%Y-%m-%dT%H:%M:00+05:30"),
        timeMax=end_dt.strftime("%Y-%m-%dT%H:%M:00+05:30"),
        singleEvents=True
    ).execute()
    
    for e in result.get("items", []):
        if e.get("extendedProperties", {}).get("private", {}).get("source") == "skedioai":
            event_start = e["start"].get("dateTime", "")
            event_end = e["end"].get("dateTime", "")
            
            expected_start = start_dt.strftime("%Y-%m-%dT%H:%M:00+05:30")
            expected_end = end_dt.strftime("%Y-%m-%dT%H:%M:00+05:30")
            
            if event_start != expected_start or event_end != expected_end:
                continue

            if match_key:
                subject, topic = match_key.split("|")
                expected_title = f"{subject} - {topic}"
                if e.get("summary", "") != expected_title:
                    continue

            e["extendedProperties"]["private"]["is_completed"] = str(completed).lower()
            if completed:
                e["colorId"] = "10"
            else:
                e.pop("colorId", None)
            service.events().update(calendarId=calendar_id, eventId=e["id"], body=e).execute()
            return f"{'Completed' if completed else 'Reopened'}: {e['summary']}"
    return "Not found"

def get_non_skedioai_events_core(start_date: str, end_date: str, user_id: str = None) -> str:
    service, calendar_id = get_service_for_user_or_default(user_id)
    try:
        result = service.events().list(
            calendarId=calendar_id,
            timeMin=_ensure_utc(f"{start_date}T00:00:00"),
            timeMax=_ensure_utc(f"{end_date}T23:59:59"),
            singleEvents=True, orderBy="startTime"
        ).execute()
        
        blocked = []
        for e in result.get("items", []):
            source = e.get("extendedProperties", {}).get("private", {}).get("source", "")
            
            if source != "skedioai":
                start_raw = e["start"].get("dateTime", e["start"].get("date"))
                end_raw = e["end"].get("dateTime", e["end"].get("date"))
                
                if "T" in start_raw:
                    start_dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
                    end_dt = datetime.fromisoformat(end_raw.replace("Z", "+00:00"))
                    blocked.append({
                        "date": start_dt.strftime("%Y-%m-%d"),
                        "start_time": start_dt.strftime("%H:%M"),
                        "end_time": end_dt.strftime("%H:%M"),
                        "title": e.get("summary", "Event")
                    })
            elif source == "skedioai":
                is_completed = e.get("extendedProperties", {}).get("private", {}).get("is_completed", "false")
                if is_completed == "true":
                    start_raw = e["start"].get("dateTime", e["start"].get("date"))
                    end_raw = e["end"].get("dateTime", e["end"].get("date"))
                    
                    if "T" in start_raw:
                        start_dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
                        end_dt = datetime.fromisoformat(end_raw.replace("Z", "+00:00"))
                        blocked.append({
                            "date": start_dt.strftime("%Y-%m-%d"),
                            "start_time": start_dt.strftime("%H:%M"),
                            "end_time": end_dt.strftime("%H:%M"),
                            "title": e.get("summary", "Completed") + " (completed)"
                        })
        
        return json.dumps({
            "has_blocks": bool(blocked),
            "blocked_slots": blocked,
            "summary": f"Found {len(blocked)} blocked slots"
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})
    

if __name__ == "__main__":
    # import datetime
    # now = datetime.datetime.now()
    # start = now.isoformat()
    # end = (now + datetime.timedelta(hours=1)).isoformat()
    
    # print(f"🚨 FORCING A TEST EVENT FOR TODAY: {now.strftime('%Y-%m-%d %H:%M')}")
    # res = create_event_core(
    #     summary="!!!! TRACER EVENT - LOOK AT CALENDAR NOW !!!!",
    #     description="Testing if API matches UI",
    #     start_iso=start,
    #     end_iso=end
    # )
    # resi=delete_skedioai_events_in_range_core(start, end)
    # print(resi)/
    res = delete_skedioai_events_in_range_core(time_min_iso="2026-01-01T00:00:00+05:30",time_max_iso="2026-03-31T23:59:59+05:30")
    print(res)
