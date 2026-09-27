"""Local Postgres-backed password hashing and access-token helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time


def _auth_secret() -> bytes:
    secret = os.getenv("AUTH_SECRET") or os.getenv("DEV_AUTH_TOKEN") or "ecopulse-local-dev-secret"
    return secret.encode("utf-8")


def hash_password(password: str) -> str:
    """PBKDF2-SHA256 password hash with a random salt."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return f"pbkdf2_sha256$120000${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash or not password_hash.startswith("pbkdf2_sha256$"):
        return False
    try:
        _, iterations_s, salt_b64, digest_b64 = password_hash.split("$", 3)
        iterations = int(iterations_s)
        salt = base64.urlsafe_b64decode(salt_b64.encode())
        expected = base64.urlsafe_b64decode(digest_b64.encode())
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def create_access_token(user_id: str, *, expires_in_seconds: int = 60 * 60 * 24 * 7) -> str:
    """Create a signed bearer token: base64(user_id|expiry|signature)."""
    expiry = int(time.time()) + expires_in_seconds
    payload = f"{user_id}|{expiry}"
    signature = hmac.new(_auth_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    token = f"{payload}|{signature}"
    return base64.urlsafe_b64encode(token.encode("utf-8")).decode("utf-8")


def verify_access_token(token: str) -> str | None:
    """Return user_id when the token is valid; otherwise None."""
    if not token:
        return None
    try:
        raw = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
        user_id, expiry_s, signature = raw.rsplit("|", 2)
        expiry = int(expiry_s)
    except (ValueError, TypeError):
        return None
    if expiry < int(time.time()):
        return None
    payload = f"{user_id}|{expiry}"
    expected = hmac.new(_auth_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return None
    return user_id
