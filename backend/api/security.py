from __future__ import annotations

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.db import models
from backend.db.database import get_db
from backend.db.supabase_client import get_supabase

bearer_scheme = HTTPBearer(auto_error=False)


def get_remediation_actor(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.UserProfile:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication is required for remediation actions")
    try:
        response = get_supabase().auth.get_user(credentials.credentials)
        auth_user = response.user
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired access token") from exc
    if auth_user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")
    profile = db.query(models.UserProfile).filter_by(id=auth_user.id).first()
    if profile is None:
        raise HTTPException(status_code=403, detail="No application profile is linked to this account")
    return profile


def ensure_org_access(actor: models.UserProfile, org_id: str) -> None:
    if actor.org_id != org_id:
        raise HTTPException(status_code=403, detail="This organization is not available to your account")