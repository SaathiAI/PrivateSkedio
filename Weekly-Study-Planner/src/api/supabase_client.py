"""
Supabase Client for SkedioAI
Handles auth and database connections.
"""

import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_ANON_KEY")


def get_supabase() -> Client:
    """Get Supabase client for authenticated requests."""
    return create_client(supabase_url, supabase_key)
