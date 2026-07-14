"""
Email MCP Server for SkedioAI Study Monitor
Provides tools to check for missed study sessions and send alert emails.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
import json

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP

load_dotenv()

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

mcp = FastMCP("email_mcp")


def get_user_alert_email(user_id: str) -> str:
    """
    Get alert email for a user from Supabase profile.
    Falls back to login email if alert_email not set.

    Args:
        user_id: The user's UUID from Supabase Auth

    Returns:
        The email address to send alerts to
    """
    from src.api.user_email import get_user_alert_email as _get_email

    return _get_email(user_id)


# ─────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────
def _parse_calendar_datetime(raw_value: str) -> datetime:
    parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _get_missed_skedioai_events(user_id: str, threshold_minutes: int = 30) -> List[Dict[str, Any]]:
    """
    Internal helper to fetch missed skedioai events from Google Calendar.
    NOW checks is_completed flag - only alerts on incomplete events.

    Returns:
        List of missed events with title, start, end, event_id
    """
    from src.api.calendar_service import get_calendar_service_for_user

    service, calendar_id = get_calendar_service_for_user(user_id)
    now = datetime.now(timezone.utc)

    time_min = (now - timedelta(hours=24)).isoformat()
    time_max = (now - timedelta(minutes=threshold_minutes)).isoformat()

    result = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    missed = []
    cutoff_time = now - timedelta(minutes=threshold_minutes)

    for e in result.get("items", []):
        props = e.get("extendedProperties", {}).get("private", {})
        source = props.get("source", "")
        is_completed = props.get("is_completed", "false")
        alert_sent = props.get("missed_alert_sent", "false")

        # Check if it's an incomplete skedioai event
        if source == "skedioai" and is_completed == "false" and alert_sent != "true":
            raw_end = e["end"].get("dateTime", e["end"].get("date"))
            event_end_dt = _parse_calendar_datetime(raw_end)

            if event_end_dt <= cutoff_time:
                missed.append(
                    {
                        "title": e.get("summary", "Unnamed Event"),
                        "start": e["start"].get("dateTime", e["start"].get("date")),
                        "end": raw_end,
                        "event_id": e.get("id"),
                        "private": props,
                    }
                )

    return missed


def _mark_missed_alerts_sent(user_id: str, missed_events: List[Dict[str, Any]]) -> None:
    if not missed_events:
        return

    from src.api.calendar_service import get_calendar_service_for_user

    service, calendar_id = get_calendar_service_for_user(user_id)
    now = datetime.now(timezone.utc).isoformat()
    for event in missed_events:
        event_id = event.get("event_id")
        if not event_id:
            continue
        private_props = {
            **(event.get("private") or {}),
            "missed_alert_sent": "true",
            "missed_alert_sent_at": now,
        }
        service.events().patch(
            calendarId=calendar_id,
            eventId=event_id,
            body={"extendedProperties": {"private": private_props}},
        ).execute()


def _send_alert_email(
    missed_events: List[Dict[str, Any]], recipient: str, agent_response=""
) -> None:
    """
    Internal helper to send HTML alert email via Gmail SMTP.

    Args:
        missed_events: List of missed events to include in email
        recipient: Email address to send alert to
    """
    if not GMAIL_USER or not GMAIL_PASSWORD:
        raise RuntimeError("GMAIL_USER and GMAIL_APP_PASSWORD are required for email alerts")

    rows = ""
    for e in missed_events:
        rows += f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #eee;">{e["title"]}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;">{e["start"]}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;">{e["end"]}</td>
        </tr>"""

    html = f"""
    <html>
    <body style="font-family:Arial,sans-serif;color:#333;max-width:600px;margin:auto;">
        <div style="background:#4F46E5;padding:20px;border-radius:8px 8px 0 0;">
            <h2 style="color:white;margin:0;">📚 SkedioAI Study Monitor</h2>
        </div>
        <div style="padding:20px;background:#f9f9f9;border-radius:0 0 8px 8px;">
            <p>Hey! Looks like you missed <strong>{len(missed_events)}</strong> study session(s).</p>
            <table style="width:100%;border-collapse:collapse;background:white;border-radius:8px;overflow:hidden;">
                <thead>
                    <tr style="background:#4F46E5;color:white;">
                        <th style="padding:10px;text-align:left;">Session</th>
                        <th style="padding:10px;text-align:left;">Start</th>
                        <th style="padding:10px;text-align:left;">End</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
            {f"<div style='background:white;padding:15px;margin:15px 0;border-radius:8px;'><pre style='white-space:pre-wrap;'>{agent_response}</pre></div>" if agent_response else ""}
            <p style="margin-top:20px;">Open SkedioAI and say <em>"I missed some sessions"</em> to reschedule 💪</p>
            <p style="color:#999;font-size:12px;">— SkedioAI Monitor Agent</p>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"⚠️ SkedioAI Alert: {len(missed_events)} Missed Study Session(s)"
    msg["From"] = GMAIL_USER
    msg["To"] = recipient
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_USER, recipient, msg.as_string())


def send_success_email(
    *,
    missed_events: list,
    recipient: str,
    agent_response: str = "",
) -> None:
    """
    Send green success email when auto-reschedule succeeded.
    missed_events: list of dicts with keys: title, start, end
    """
    if not GMAIL_USER or not GMAIL_PASSWORD:
        raise RuntimeError("GMAIL_USER and GMAIL_APP_PASSWORD are required")

    rows = ""
    for e in missed_events:
        rows += f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #eee;">{e.get("title", "")}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;">{e.get("start", "")}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;">{e.get("end", "")}</td>
        </tr>"""

    html = f"""
    <html>
    <body style="font-family:Arial,sans-serif;color:#333;max-width:600px;margin:auto;">
        <div style="background:#22c55e;padding:20px;border-radius:8px 8px 0 0;">
            <h2 style="color:white;margin:0;">&#x2705; SkedioAI Auto-Rescheduled</h2>
        </div>
        <div style="padding:20px;background:#f9f9f9;border-radius:0 0 8px 8px;">
            <p>SkedioAI automatically moved your conflicting sessions:</p>
            <table style="width:100%;border-collapse:collapse;background:white;border-radius:8px;overflow:hidden;">
                <thead>
                    <tr style="background:#22c55e;color:white;">
                        <th style="padding:10px;text-align:left;">Session</th>
                        <th style="padding:10px;text-align:left;">Moved From</th>
                        <th style="padding:10px;text-align:left;">New Time</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
            {f"<div style='background:white;padding:15px;margin:15px 0;border-radius:8px;'><pre style='white-space:pre-wrap;'>{agent_response}</pre></div>" if agent_response else ""}
            <p style="margin-top:20px;">Check your calendar for updated timings &#x1F4C5;</p>
            <p style="color:#999;font-size:12px;">&#x2014; SkedioAI Monitor Agent</p>
        </div>
    </body>
    </html>
    """

    subject = f"&#x2705; SkedioAI: Sessions auto-rescheduled"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = recipient
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_USER, recipient, msg.as_string())


def send_plan_review_email(
    *,
    recipient: str,
    subject_line: str,
    intro: str,
    sessions: list[dict[str, Any]],
    agent_response: str = "",
    approve_url: str,
    request_changes_url: str,
    open_url: str,
) -> None:
    """Send a review email for a pending planner draft."""

    if not GMAIL_USER or not GMAIL_PASSWORD:
        raise RuntimeError("GMAIL_USER and GMAIL_APP_PASSWORD are required")

    session_count = len(sessions)
    session_cards = ""
    for index, session in enumerate(sessions, start=1):
        border_style = "border-bottom:1px solid #ececf4;" if index < session_count else ""
        session_cards += f"""
        <tr>
          <td style="padding:0;">
            <div style="{border_style}padding:16px 18px;">
              <div style="font-size:15px;line-height:1.4;font-weight:700;color:#171923;margin:0 0 8px;">
                {session.get("title", "Study Session")}
              </div>
              <div style="font-size:13px;line-height:1.6;color:#5b6472;">
                <span style="display:inline-block;min-width:86px;color:#7a8494;">Start</span>
                <span style="font-weight:600;color:#1f2937;">{session.get("start", "")}</span>
              </div>
              <div style="font-size:13px;line-height:1.6;color:#5b6472;">
                <span style="display:inline-block;min-width:86px;color:#7a8494;">End</span>
                <span style="font-weight:600;color:#1f2937;">{session.get("end", "")}</span>
              </div>
            </div>
          </td>
        </tr>"""

    note_block = ""
    if agent_response:
        note_block = f"""
        <div style="margin-top:20px;background:#f7f8fc;border:1px solid #e7e9f2;border-radius:18px;padding:18px 20px;">
          <div style="font-size:11px;letter-spacing:0.08em;text-transform:uppercase;font-weight:700;color:#6b7280;margin-bottom:10px;">
            Note
          </div>
          <div style="font-size:14px;line-height:1.75;color:#1f2937;white-space:pre-wrap;">{agent_response}</div>
        </div>"""

    html = f"""
    <html>
    <body style="margin:0;padding:0;background:#eef1f7;font-family:Arial,sans-serif;color:#111827;">
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#eef1f7;padding:24px 0;">
        <tr>
          <td align="center">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:680px;margin:0 auto;">
              <tr>
                <td style="padding:0 16px;">
                  <div style="background:#ffffff;border:1px solid #dde3ee;border-radius:28px;overflow:hidden;box-shadow:0 24px 60px rgba(36,42,66,0.10);">
                    <div style="background:linear-gradient(135deg,#5b5cf0 0%,#7c8cff 100%);padding:28px 28px 24px;">
                      <div style="font-size:11px;letter-spacing:0.10em;text-transform:uppercase;font-weight:700;color:#dfe3ff;margin-bottom:12px;">
                        Study plan update
                      </div>
                      <div style="font-size:30px;line-height:1.18;font-weight:700;color:#ffffff;margin:0 0 10px;">
                        Your study plan was adjusted
                      </div>
                      <div style="font-size:15px;line-height:1.7;color:#edf1ff;max-width:540px;">
                        {intro}
                      </div>
                    </div>

                    <div style="padding:22px 24px 8px;background:#ffffff;">
                      <div style="background:#f6f7ff;border:1px solid #e4e7fb;border-radius:18px;padding:16px 18px;">
                        <div style="font-size:13px;line-height:1.75;color:#3d4653;">
                          I updated the affected study sessions around your latest calendar change.
                          Nothing is saved until you approve this draft.
                        </div>
                      </div>

                      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-top:18px;">
                        <tr>
                          <td width="33.33%" style="padding:0 6px 0 0;">
                            <div style="background:#fafbff;border:1px solid #e8ebf5;border-radius:18px;padding:16px 14px;">
                              <div style="font-size:10px;letter-spacing:0.08em;text-transform:uppercase;font-weight:700;color:#7c8798;">Sessions moved</div>
                              <div style="font-size:28px;line-height:1.2;font-weight:700;color:#111827;margin-top:8px;">{session_count}</div>
                            </div>
                          </td>
                          <td width="33.33%" style="padding:0 3px;">
                            <div style="background:#fafbff;border:1px solid #e8ebf5;border-radius:18px;padding:16px 14px;">
                              <div style="font-size:10px;letter-spacing:0.08em;text-transform:uppercase;font-weight:700;color:#7c8798;">Review state</div>
                              <div style="font-size:20px;line-height:1.2;font-weight:700;color:#111827;margin-top:12px;">Waiting</div>
                            </div>
                          </td>
                          <td width="33.33%" style="padding:0 0 0 6px;">
                            <div style="background:#fafbff;border:1px solid #e8ebf5;border-radius:18px;padding:16px 14px;">
                              <div style="font-size:10px;letter-spacing:0.08em;text-transform:uppercase;font-weight:700;color:#7c8798;">Next step</div>
                              <div style="font-size:20px;line-height:1.2;font-weight:700;color:#111827;margin-top:12px;">Review</div>
                            </div>
                          </td>
                        </tr>
                      </table>

                      <div style="margin-top:22px;border-radius:22px;overflow:hidden;border:1px solid #e6e9f2;background:#ffffff;">
                        <div style="padding:18px 20px;background:#171c27;">
                          <div style="font-size:11px;letter-spacing:0.09em;text-transform:uppercase;font-weight:700;color:#aeb7c8;margin-bottom:6px;">
                            Updated sessions
                          </div>
                          <div style="font-size:22px;line-height:1.25;font-weight:700;color:#ffffff;">
                            Here is the updated draft
                          </div>
                        </div>
                        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#ffffff;">
                          {session_cards}
                        </table>
                      </div>

                      {note_block}

                      <div style="margin-top:24px;">
                        <a href="{approve_url}" style="display:inline-block;background:#5b5cf0;color:#ffffff;padding:14px 20px;border-radius:999px;text-decoration:none;font-size:14px;font-weight:700;margin-right:10px;margin-bottom:10px;">Approve</a>
                        <a href="{request_changes_url}" style="display:inline-block;background:#ffffff;color:#202938;padding:14px 20px;border-radius:999px;border:1px solid #d5daea;text-decoration:none;font-size:14px;font-weight:700;margin-right:10px;margin-bottom:10px;">Change it</a>
                        <a href="{open_url}" style="display:inline-block;background:#eef2ff;color:#4f46e5;padding:14px 20px;border-radius:999px;text-decoration:none;font-size:14px;font-weight:700;margin-bottom:10px;">Open app</a>
                      </div>

                      <div style="margin-top:18px;padding-top:18px;border-top:1px solid #eceff6;font-size:12px;line-height:1.7;color:#6b7280;">
                        Open the app if you want to check the draft before deciding.
                      </div>
                    </div>
                  </div>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject_line
    msg["From"] = GMAIL_USER
    msg["To"] = recipient
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_USER, recipient, msg.as_string())


# ─────────────────────────────────────────────
# MCP Tools
# ─────────────────────────────────────────────


class CheckMissedSessionsInput(BaseModel):
    """Input model for checking missed study sessions."""

    model_config = ConfigDict(
        str_strip_whitespace=True, validate_assignment=True, extra="forbid"
    )

    user_id: str = Field(
        ...,
        description="User ID whose connected Google Calendar should be checked",
    )
    threshold_minutes: int = Field(
        default=30,
        description="How many minutes after session end to consider it 'missed'",
        ge=1,
        le=180,
    )


@mcp.tool(
    name="check_missed_sessions",
    annotations={
        "title": "Check for Missed Study Sessions",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def check_missed_sessions(params: CheckMissedSessionsInput) -> str:
    """
    Check for skedioai study sessions that ended more than threshold_minutes ago.

    This tool queries the Google Calendar for skedioai events that have ended
    but haven't been acknowledged within the threshold time.

    Args:
        params (CheckMissedSessionsInput): Contains:
            - threshold_minutes (Optional[int]): Minutes after end to consider missed (default: 30)

    Returns:
        str: JSON-formatted response with:
            - has_missed (bool): Whether any missed sessions were found
            - count (int): Number of missed sessions
            - sessions (List[Dict]): List of missed sessions with title, start, end
            - message (str): Human-readable summary
    """

    missed = _get_missed_skedioai_events(
        user_id=params.user_id,
        threshold_minutes=params.threshold_minutes,
    )

    if not missed:
        response = {
            "has_missed": False,
            "count": 0,
            "sessions": [],
            "message": "No missed skedioai sessions found.",
        }
    else:
        response = {
            "has_missed": True,
            "count": len(missed),
            "sessions": missed,
            "message": f"Found {len(missed)} missed session(s)",
        }

    return json.dumps(response, indent=2)


class SendAlertEmailInput(BaseModel):
    """Input model for sending alert emails."""

    model_config = ConfigDict(
        str_strip_whitespace=True, validate_assignment=True, extra="forbid"
    )

    user_id: str = Field(
        ...,
        description="User ID to look up alert email from their profile",
    )
    missed_sessions: List[Dict[str, Any]] = Field(
        ...,
        description="List of missed sessions, each with 'title', 'start', 'end' keys",
    )


@mcp.tool(
    name="send_alert_email",
    annotations={
        "title": "Send Missed Session Alert Email",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def send_alert_email(params: SendAlertEmailInput) -> str:
    """
    Send an HTML-formatted alert email about missed study sessions.

    This tool sends a professionally formatted email via Gmail SMTP with
    a table of missed sessions and action items.

    Args:
        params (SendAlertEmailInput): Contains:
            - user_id (str): User ID to look up their alert email from profile
            - missed_sessions (List[Dict]): Sessions with 'title', 'start', 'end'

    Returns:
        str: JSON-formatted response with:
            - success (bool): Whether email was sent successfully
            - recipient (str): Email address sent to
            - count (int): Number of sessions included
            - message (str): Status message
    """
    try:
        recipient = get_user_alert_email(params.user_id)
        _send_alert_email(params.missed_sessions, recipient)

        response = {
            "success": True,
            "recipient": recipient,
            "count": len(params.missed_sessions),
            "message": f"✅ Alert email sent to {recipient} for {len(params.missed_sessions)} missed session(s)",
        }

        return json.dumps(response, indent=2)

    except Exception as e:
        response = {
            "success": False,
            "recipient": "unknown",
            "count": len(params.missed_sessions),
            "error": str(e),
            "message": f"❌ Failed to send email: {str(e)}",
        }

        return json.dumps(response, indent=2)


def mark_missed_alerts_sent(user_id: str, missed_events: List[Dict[str, Any]]) -> None:
    _mark_missed_alerts_sent(user_id, missed_events)


# ─────────────────────────────────────────────
# Server Entry Point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
