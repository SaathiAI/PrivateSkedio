"""
SkedioAI API Module
Exports auth, calendar, and profile components.
"""

from src.api.auth import get_current_user
from src.api.supabase_client import get_supabase
from src.api.calendar_service import (
    get_calendar_service_for_user,
    is_calendar_connected,
)
from src.api.user_email import get_user_alert_email, get_user_login_email

__all__ = [
    "get_current_user",
    "get_supabase",
    "get_calendar_service_for_user",
    "is_calendar_connected",
    "get_user_alert_email",
    "get_user_login_email",
]
