"""
Monitor Script for SkedioAI Email Alerts
Runs every 30 minutes to check for missed study sessions and send alerts.
"""

import schedule
import time
import asyncio
from datetime import datetime

# Import the MCP tools directly
from src.api.calendar_service import get_supabase
from src.mcp_servers.email_mcp_server import (
    CheckMissedSessionsInput,
    SendAlertEmailInput,
    check_missed_sessions,
    mark_missed_alerts_sent,
    send_alert_email,
)
import json


def get_connected_calendar_user_ids() -> list[str]:
    """Return users who have connected Google Calendar tokens."""
    result = (
        get_supabase()
        .table("user_settings")
        .select("user_id, google_access_token, google_refresh_token")
        .execute()
    )
    return [
        row["user_id"]
        for row in result.data or []
        if row.get("user_id") and row.get("google_access_token") and row.get("google_refresh_token")
    ]


async def check_and_send_alerts():
    """Check for missed sessions and send email if any found."""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking for missed sessions...")
    user_ids = get_connected_calendar_user_ids()
    print(f"Found {len(user_ids)} connected calendar user(s)")

    for user_id in user_ids:
        try:
            params = CheckMissedSessionsInput(user_id=user_id, threshold_minutes=30)
            result = await check_missed_sessions(params)
            result_data = json.loads(result)

            if not result_data["has_missed"]:
                print(f"No missed sessions for user {user_id}")
                continue

            print(
                f"Found {result_data['count']} missed session(s) for user {user_id}; sending alert"
            )
            missed_sessions = result_data["sessions"]
            email_params = SendAlertEmailInput(
                user_id=user_id,
                missed_sessions=missed_sessions,
            )
            email_result = await send_alert_email(email_params)
            email_data = json.loads(email_result)

            if email_data["success"]:
                mark_missed_alerts_sent(user_id, missed_sessions)
                print(f"Alert email sent successfully to {email_data.get('recipient')}")
            else:
                print(f"Failed to send email for user {user_id}: {email_data.get('error', 'Unknown error')}")
        except Exception as exc:
            print(f"Monitor failed for user {user_id}: {exc}")


def run_check():
    """Wrapper to run async check function."""
    asyncio.run(check_and_send_alerts())


def main():
    """Main monitor loop - runs checks every 30 minutes."""
    print("🚀 Starting SkedioAI Email Monitor")
    print("📧 Alert users: all users with connected Google Calendar")
    print(f"⏱️  Checking every 30 minutes for missed sessions")
    print("─" * 60)
    
    # Run immediately on start
    print("\n🔄 Running initial check...")
    run_check()
    
    # Schedule to run every 30 minutes
    schedule.every(30).minutes.do(run_check)
    
    print(f"\n✅ Monitor started. Next check in 30 minutes.")
    print("Press Ctrl+C to stop.\n")
    
    # Keep running
    while True:
        schedule.run_pending()
        time.sleep(60)  


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Monitor stopped by user.")
    except Exception as e:
        print(f"\n\n❌ Monitor error: {e}")
