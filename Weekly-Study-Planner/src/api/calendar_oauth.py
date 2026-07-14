"""
Calendar OAuth Endpoints for SkedioAI
Handles Google Calendar OAuth flow for per-user calendar access.
"""

import os
import secrets
import time
import hmac
import json
import base64
import hashlib
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import create_client
from dotenv import load_dotenv
from src.api.auth import get_current_user

load_dotenv()

router = APIRouter(prefix="/auth/calendar", tags=["calendar_oauth"])

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
CALENDAR_OAUTH_STATE_SECRET = (
    os.getenv("CALENDAR_OAUTH_STATE_SECRET")
    or os.getenv("APP_SECRET")
    or GOOGLE_CLIENT_SECRET
    or "dev-calendar-oauth-secret"
)


def get_supabase():
    if not SUPABASE_URL:
        raise HTTPException(status_code=503, detail="SUPABASE_URL is not configured")
    if not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(
            status_code=503,
            detail="SUPABASE_SERVICE_ROLE_KEY is required for Calendar token storage",
        )
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
CALLBACK_URL = os.getenv(
    "GOOGLE_CALENDAR_CALLBACK_URL",
    "http://localhost:8000/auth/calendar/callback",
)


def _base64_url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _base64_url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("utf-8"))


def _sign_state_payload(payload: dict) -> str:
    body = _base64_url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(
        CALENDAR_OAUTH_STATE_SECRET.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return f"{body}.{_base64_url_encode(signature)}"


def _verify_state_payload(state: str) -> dict:
    try:
        body, signature = state.split(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid calendar OAuth state") from exc

    expected_signature = hmac.new(
        CALENDAR_OAUTH_STATE_SECRET.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    provided_signature = _base64_url_decode(signature)
    if not hmac.compare_digest(expected_signature, provided_signature):
        raise HTTPException(status_code=400, detail="Invalid calendar OAuth state")

    payload = json.loads(_base64_url_decode(body).decode("utf-8"))
    if int(payload.get("exp", 0)) < int(time.time()):
        raise HTTPException(status_code=400, detail="Calendar OAuth state expired")
    if not payload.get("user_id"):
        raise HTTPException(status_code=400, detail="Calendar OAuth state missing user")
    return payload


def _allowed_frontend_origins() -> set[str]:
    origins = {FRONTEND_URL.rstrip("/")}
    extra = os.getenv("ALLOWED_FRONTEND_ORIGINS", "")
    origins.update(origin.strip().rstrip("/") for origin in extra.split(",") if origin.strip())
    origins.update({"http://localhost:3000", "http://localhost:5173"})
    return origins


def _safe_return_url(return_url: str | None) -> str:
    if not return_url:
        return FRONTEND_URL.rstrip("/")

    clean_url = return_url.rstrip("/")
    if clean_url in _allowed_frontend_origins():
        return clean_url

    if clean_url.startswith("https://") and clean_url.endswith(".vercel.app"):
        return clean_url

    return FRONTEND_URL.rstrip("/")


async def _exchange_google_calendar_code(code: str) -> dict:
    import httpx

    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")

    async with httpx.AsyncClient(timeout=12) as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": CALLBACK_URL,
                "grant_type": "authorization_code",
            },
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=400, detail=f"Token exchange failed: {response.text}"
        )
    return response.json()


def _store_calendar_tokens(user_id: str, tokens: dict) -> None:
    from datetime import datetime, timedelta, timezone

    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    expires_in = tokens.get("expires_in")
    expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in or 3600)

    supabase = get_supabase()
    existing = (
        supabase.table("user_settings")
        .select("google_refresh_token")
        .eq("user_id", user_id)
        .execute()
    )
    existing_refresh_token = None
    if existing.data:
        existing_refresh_token = existing.data[0].get("google_refresh_token")

    supabase.table("user_settings").upsert(
        {
            "user_id": user_id,
            "google_access_token": access_token,
            "google_refresh_token": refresh_token or existing_refresh_token,
            "google_token_expiry": expiry.isoformat(),
            "calendar_id": "primary",
        }
    ).execute()


@router.get("/connect")
async def connect_calendar(
    return_url: str | None = Query(default=None),
    user_id: str = Depends(get_current_user),
):
    """
    Returns the Google OAuth URL. Frontend does window.location.href to this URL.
    No CORS issue — it's a top-level browser navigation, not a fetch call.
    """
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")

    safe_return_url = _safe_return_url(return_url)
    state = _sign_state_payload(
        {
            "user_id": user_id,
            "return_url": safe_return_url,
            "nonce": secrets.token_urlsafe(16),
            "exp": int(time.time()) + 10 * 60,
        }
    )
    query = urlencode(
        {
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": CALLBACK_URL,
            "response_type": "code",
            "scope": "https://www.googleapis.com/auth/calendar",
            "access_type": "offline",
            "prompt": "consent select_account",
            "state": state,
        }
    )

    return {
        "auth_url": f"https://accounts.google.com/o/oauth2/v2/auth?{query}",
        "state": state,
    }


@router.get("/callback")
async def calendar_callback(
    code: str | None = Query(default=None),
    state: str = Query(default=""),
    error: str | None = Query(default=None),
):
    """
    Google redirects here after user authorizes Calendar access.
    Backend owns the token exchange, then redirects the user back to Settings.
    """
    from fastapi.responses import RedirectResponse

    if error:
        query = urlencode({"calendar_status": "error", "calendar_message": error})
        return RedirectResponse(url=f"{FRONTEND_URL.rstrip('/')}/?{query}", status_code=302)

    if not code:
        query = urlencode(
            {
                "calendar_status": "error",
                "calendar_message": "Google did not return an authorization code",
            }
        )
        return RedirectResponse(url=f"{FRONTEND_URL.rstrip('/')}/?{query}", status_code=302)

    try:
        payload = _verify_state_payload(state)
        tokens = await _exchange_google_calendar_code(code)
        _store_calendar_tokens(payload["user_id"], tokens)
    except Exception as exc:
        message = getattr(exc, "detail", None) or str(exc)
        query = urlencode({"calendar_status": "error", "calendar_message": message})
        return RedirectResponse(url=f"{FRONTEND_URL.rstrip('/')}/?{query}", status_code=302)

    return_url = _safe_return_url(payload.get("return_url"))
    query = urlencode({"calendar_status": "connected"})
    return RedirectResponse(url=f"{return_url}/?{query}", status_code=302)


@router.get("/status")
async def calendar_status(user_id: str = Depends(get_current_user)):
    """
    Check if user has connected Google Calendar.
    """
    supabase = get_supabase()

    result = (
        supabase.table("user_settings")
        .select("google_access_token", "google_refresh_token", "calendar_id")
        .eq("user_id", user_id)
        .execute()
    )

    if not result.data or not result.data[0].get("google_access_token"):
        return {"connected": False, "message": "Calendar not connected"}

    return {
        "connected": True,
        "calendar_id": result.data[0].get("calendar_id", "primary"),
    }


@router.post("/disconnect")
async def disconnect_calendar(user_id: str = Depends(get_current_user)):
    """
    Remove Google Calendar connection from user settings.
    """
    supabase = get_supabase()

    supabase.table("user_settings").update(
        {
            "google_access_token": None,
            "google_refresh_token": None,
            "google_token_expiry": None,
        }
    ).eq("user_id", user_id).execute()

    return {"status": "disconnected", "message": "Calendar disconnected"}
