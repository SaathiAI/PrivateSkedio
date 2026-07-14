"""
Auth Middleware for SkedioAI
Verifies JWT tokens and extracts user_id.
"""

from __future__ import annotations

import logging
import os
import threading
import time

from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

supabase_url = os.getenv("SUPABASE_URL")
supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")
AUTH_CACHE_TTL_SECONDS = int(os.getenv("AUTH_CACHE_TTL_SECONDS", "120"))

security = HTTPBearer(auto_error=False)
logger = logging.getLogger("skedioai.perf.auth")

_supabase_client = (
    create_client(supabase_url, supabase_anon_key)
    if supabase_url and supabase_anon_key
    else None
)
_auth_cache: dict[str, tuple[str, float]] = {}
_auth_cache_lock = threading.Lock()


def _get_cached_user_id(token: str) -> str | None:
    now = time.time()
    with _auth_cache_lock:
        cached = _auth_cache.get(token)
        if not cached:
            return None
        user_id, expires_at = cached
        if expires_at <= now:
            _auth_cache.pop(token, None)
            return None
        return user_id


def _store_cached_user_id(token: str, user_id: str) -> None:
    expires_at = time.time() + AUTH_CACHE_TTL_SECONDS
    with _auth_cache_lock:
        _auth_cache[token] = (user_id, expires_at)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """
    Dependency that extracts user_id from JWT token.
    Use in routes: async def my_route(user_id: str = Depends(get_current_user))
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    token = credentials.credentials
    cached_user_id = _get_cached_user_id(token)
    if cached_user_id:
        logger.info(
            "stage=auth_validate cache=hit duration_ms=0 user_id=%s",
            cached_user_id,
        )
        return cached_user_id

    if _supabase_client is None:
        raise HTTPException(status_code=503, detail="Authentication is not configured")

    started_at = time.perf_counter()
    try:
        user_response = _supabase_client.auth.get_user(token)
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid token")
        user_id = user_response.user.id
        _store_cached_user_id(token, user_id)
        logger.info(
            "stage=auth_validate cache=miss duration_ms=%s user_id=%s",
            round((time.perf_counter() - started_at) * 1000, 2),
            user_id,
        )
        return user_id
    except Exception as e:
        logger.warning(
            "stage=auth_validate cache=miss duration_ms=%s error=%s",
            round((time.perf_counter() - started_at) * 1000, 2),
            str(e),
        )
        raise HTTPException(status_code=401, detail="Authentication failed")
