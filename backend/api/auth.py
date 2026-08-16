"""
Auth endpoints — org signup + login, backed by Supabase Auth.

  POST /auth/signup  -> creates a Supabase Auth user, a new Organization,
                         and a UserProfile (role="admin") linking them.
                         This is how a NEW company/tenant onboards.
  POST /auth/login   -> verifies credentials via Supabase Auth, returns the
                         session (access_token) plus the caller's org_id/role.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db.supabase_client import get_supabase
from backend.db import models

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    org_name: str
    full_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/signup")
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    """Creates a brand-new organization with the caller as its first admin."""
    supabase = get_supabase()

    auth_result = supabase.auth.sign_up({"email": payload.email, "password": payload.password})
    if not auth_result.user:
        raise HTTPException(status_code=400, detail="Supabase signup failed")

    org = models.Organization(name=payload.org_name)
    db.add(org)
    db.flush()  # get org.id

    profile = models.UserProfile(
        id=auth_result.user.id,
        org_id=org.id,
        full_name=payload.full_name,
        role="admin",  # first user of a new org is always its admin
    )
    db.add(profile)
    db.commit()

    return {
        "user_id": auth_result.user.id,
        "org_id": org.id,
        "role": "admin",
        "note": "Check your email to confirm the account if Supabase email confirmation is enabled.",
    }


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Verifies credentials via Supabase Auth and returns the session + org context."""
    supabase = get_supabase()

    try:
        auth_result = supabase.auth.sign_in_with_password(
            {"email": payload.email, "password": payload.password}
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    profile = db.query(models.UserProfile).filter_by(id=auth_result.user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile found for this user")

    return {
        "access_token": auth_result.session.access_token,
        "user_id": auth_result.user.id,
        "org_id": profile.org_id,
        "role": profile.role,
    }
