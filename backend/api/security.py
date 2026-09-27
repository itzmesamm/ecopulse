"""Local Postgres authentication and organization isolation for API requests."""

from __future__ import annotations

import json
import os
from urllib.parse import parse_qs

from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.db import models
from backend.db.database import SessionLocal
from backend.db.local_auth import verify_access_token


PUBLIC_PATHS = {
    "/health",
    "/auth/signup",
    "/auth/login",
    "/auth/dev-login",
    "/openapi.json",
    "/docs",
    "/redoc",
}


class OrgAuthenticationMiddleware:
    """Authenticate API requests and reject cross-organization access."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        if request.method == "OPTIONS" or request.url.path in PUBLIC_PATHS or request.url.path.startswith(("/docs/", "/redoc/")):
            await self.app(scope, receive, send)
            return

        authorization = request.headers.get("authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            await JSONResponse({"detail": "Bearer authentication required"}, status_code=401)(scope, receive, send)
            return

        user_id = None
        if os.getenv("APP_ENV", "development").lower() != "production":
            dev_token = os.getenv("DEV_AUTH_TOKEN")
            dev_user_id = os.getenv("DEV_AUTH_USER_ID")
            if dev_token and dev_user_id and token == dev_token:
                user_id = dev_user_id
        if user_id is None:
            user_id = verify_access_token(token)
        if user_id is None:
            await JSONResponse({"detail": "Invalid or expired access token"}, status_code=401)(scope, receive, send)
            return

        db = SessionLocal()
        try:
            profile = db.query(models.UserProfile).filter_by(id=user_id).first()
            if profile is None:
                await JSONResponse({"detail": "User profile not found"}, status_code=403)(scope, receive, send)
                return
            profile_data = {"id": profile.id, "org_id": profile.org_id, "role": profile.role or "viewer"}
        finally:
            db.close()

        body = await request.body()
        query = parse_qs(scope.get("query_string", b"").decode("latin-1"))
        query_org_id = next(iter(query.get("org_id", [])), None)
        body_org_id = None
        if body:
            try:
                request_data = json.loads(body)
            except (json.JSONDecodeError, UnicodeDecodeError):
                request_data = {}
            if isinstance(request_data, dict):
                body_org_id = request_data.get("org_id")

        requested_org_ids = [value for value in (query_org_id, body_org_id) if value is not None]
        # org_id is optional on profile/helper routes (e.g. /auth/me, cloud-providers).
        # When present it must be non-empty and match the caller's organization.
        if any(not value for value in requested_org_ids):
            await JSONResponse({"detail": "org_id is required"}, status_code=400)(scope, receive, send)
            return
        if any(str(value) != profile_data["org_id"] for value in requested_org_ids):
            await JSONResponse({"detail": "Organization access denied"}, status_code=403)(scope, receive, send)
            return

        scope.setdefault("state", {})["profile"] = profile_data
        body_sent = False

        async def replay_body():
            nonlocal body_sent
            if not body_sent:
                body_sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.request", "body": b"", "more_body": False}

        await self.app(scope, replay_body, send)
