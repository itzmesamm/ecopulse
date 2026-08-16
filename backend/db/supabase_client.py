"""
Supabase client for backend-side Auth operations (signup/login).

Uses the SERVICE ROLE key — this file only ever runs on the backend, never
shipped to the frontend. The frontend should use SUPABASE_ANON_KEY with its
own supabase-js client for the actual login form later.
"""
import os
from supabase import create_client, Client
import socket

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

_client: Client | None = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env "
                "before auth endpoints will work."
            )
        # Validate that the SUPABASE_URL host resolves before attempting network calls
        try:
            host = SUPABASE_URL.split("://", 1)[1].split("/", 1)[0]
        except Exception:
            raise RuntimeError("SUPABASE_URL appears malformed; must include scheme (https://...).")

        try:
            socket.getaddrinfo(host, None)
        except socket.gaierror:
            raise RuntimeError(
                f"Unable to resolve Supabase host '{host}'.\n"
                "Check SUPABASE_URL in your .env and ensure you have network access."
            )
        try:
            _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        except Exception as e:
            raise RuntimeError(f"Failed to create Supabase client: {e}") from e
    return _client
