"""
Deprecated: EcoPulse auth now uses local Postgres credentials.

This module remains only so older imports fail clearly instead of silently
calling a remote Supabase Auth project.
"""


def get_supabase():
    raise RuntimeError(
        "Supabase Auth has been removed. Auth uses local Postgres via "
        "backend.db.local_auth (email/password + signed access tokens). "
        "Set DATABASE_URL to your Postgres instance and run alembic upgrade head."
    )
