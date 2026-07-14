"""
User Email Helper for SkedioAI
Gets user email from Supabase profile (for alerts, etc.)
"""

import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()


def get_supabase():
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url:
        raise RuntimeError("SUPABASE_URL is not configured")
    if not service_role_key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is required for email lookup")
    return create_client(supabase_url, service_role_key)


def get_user_alert_email(user_id: str) -> str:
    """
    Get the email address where alerts should be sent for a user.
    Priority: alert_email > email (login email)

    Args:
        user_id: The user's UUID from Supabase Auth

    Returns:
        The email address to send alerts to

    Raises:
        ValueError: If no email found for user
    """
    supabase = get_supabase()

    result = (
        supabase.table("profiles")
        .select("email", "alert_email")
        .eq("id", user_id)
        .execute()
    )

    if not result.data:
        raise ValueError(f"No profile found for user: {user_id}")

    profile = result.data[0]

    # Prefer alert_email if set, otherwise fall back to login email
    alert_email = profile.get("alert_email") or profile.get("email")

    if not alert_email:
        raise ValueError(f"No email found for user: {user_id}")

    return alert_email


def get_user_login_email(user_id: str) -> str | None:
    """
    Get user's login email.

    Args:
        user_id: The user's UUID from Supabase Auth

    Returns:
        The user's login email, or None if not found
    """
    supabase = get_supabase()

    result = supabase.table("profiles").select("email").eq("id", user_id).execute()

    if result.data:
        return result.data[0].get("email")

    return None
