"""
Calendar Service Helper for SkedioAI
Gets Google Calendar service for a specific user using their stored tokens.
"""

import os
from dotenv import load_dotenv
from fastapi import HTTPException
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from supabase import create_client

load_dotenv()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")


def get_supabase():
    if not SUPABASE_URL:
        raise HTTPException(status_code=503, detail="SUPABASE_URL is not configured")
    if not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(
            status_code=503,
            detail="SUPABASE_SERVICE_ROLE_KEY is required for Calendar token storage",
        )
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def get_calendar_service_for_user(user_id: str):
    """
    Get Google Calendar service for a specific user.
    Reads tokens from user_settings table in Supabase.
    """
    supabase = get_supabase()

    # Get tokens from user_settings
    result = (
        supabase.table("user_settings").select("*").eq("user_id", user_id).execute()
    )

    if not result.data:
        raise Exception("Calendar not connected. User has no settings.")

    settings = result.data[0]
    access_token = settings.get("google_access_token")
    refresh_token = settings.get("google_refresh_token")
    expiry_str = settings.get("google_token_expiry")
    calendar_id = settings.get("calendar_id", "primary")

    if not access_token or not refresh_token:
        raise Exception("Calendar not connected. No tokens found.")

    # Parse expiry
    from datetime import datetime, timezone

    expiry = None
    if expiry_str:
        parsed_expiry = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
        if parsed_expiry.tzinfo is not None:
            parsed_expiry = parsed_expiry.astimezone(timezone.utc).replace(tzinfo=None)
        expiry = parsed_expiry

    # Build credentials
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        expiry=expiry,
    )

    # Refresh if expired
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Save new tokens
        supabase.table("user_settings").update(
            {
                "google_access_token": creds.token,
                "google_token_expiry": creds.expiry.isoformat()
                if creds.expiry
                else None,
            }
        ).eq("user_id", user_id).execute()

    # Build calendar service
    return build("calendar", "v3", credentials=creds), calendar_id


def is_calendar_connected(user_id: str) -> bool:
    """Check if user has connected Google Calendar."""
    try:
        supabase = get_supabase()
        result = (
            supabase.table("user_settings")
            .select("google_access_token")
            .eq("user_id", user_id)
            .execute()
        )
        return bool(result.data and result.data[0].get("google_access_token"))
    except:
        return False
