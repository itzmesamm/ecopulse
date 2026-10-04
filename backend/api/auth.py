"""
Auth endpoints — org signup + login, backed by Supabase Auth.

  POST /auth/signup  -> creates a Supabase Auth user, a new Organization,
                         and a UserProfile (role="admin") linking them.
                         This is how a NEW company/tenant onboards.
  POST /auth/login   -> verifies credentials via Supabase Auth, returns the
                         session (access_token) plus the caller's org_id/role.
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Body
import datetime
import json
import re
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db.supabase_client import get_supabase
from backend.db import models
from backend.api.security import ensure_org_access, get_remediation_actor
from backend.remediation.cloud_credentials import encrypt_cloud_credentials

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    org_name: str
    full_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class CurrentUserResponse(BaseModel):
    user: dict
    account: dict


class CloudProviderItem(BaseModel):
    id: str
    name: str
    icon: str
    description: str


class ConnectCloudRequest(BaseModel):
    provider: str
    credentials: dict = {}


class AccessChecklistItem(BaseModel):
    item: str
    required: bool
    status: str


@router.post("/signup")
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    """Creates a brand-new organization with the caller as its first admin."""
    supabase = get_supabase()

    try:
        auth_result = supabase.auth.sign_up({
            "email": payload.email,
            "password": payload.password,
        })

    except Exception as exc:
        message = str(exc)
        message_lower = message.lower()

        # Supabase signup/email rate limiting
        if (
            "rate limit" in message_lower
            or "too many requests" in message_lower
            or "for security purposes" in message_lower
            or "only request this after" in message_lower
        ):
            raise HTTPException(
                status_code=429,
                detail=message,
            ) from exc

        # Other Supabase Auth errors
        raise HTTPException(
            status_code=502,
            detail=f"Supabase signup request failed: {message}",
        ) from exc

    if not auth_result.user:
        raise HTTPException(
            status_code=400,
            detail="Supabase signup failed",
        )

    org = models.Organization(name=payload.org_name)
    db.add(org)
    db.flush()

    profile = models.UserProfile(
        id=auth_result.user.id,
        org_id=org.id,
        full_name=payload.full_name,
        role="admin",
    )

    db.add(profile)
    db.commit()

    session = auth_result.session

    return {
        "user_id": auth_result.user.id,
        "org_id": org.id,
        "role": "admin",
        "access_token": session.access_token if session else None,
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
# ============================================================================
# User Profile & Onboarding Endpoints
# ============================================================================

@router.get("/me")
def get_current_user(
    user_id: str = Query(..., description="User ID from auth token"),
    db: Session = Depends(get_db),
) -> CurrentUserResponse:
    """
    Get current user profile and organization info.
    
    User ID is passed as query parameter (would normally come from JWT token).
    """
    profile = db.query(models.UserProfile).filter_by(id=user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")
    
    org = db.query(models.Organization).filter_by(id=profile.org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    email = ""
    try:
        sb_user = get_supabase().auth.admin.get_user_by_id(user_id)
        email = getattr(getattr(sb_user, "user", None), "email", "") or ""
    except Exception:
        email = ""

    return CurrentUserResponse(
        user={
            "id": profile.id,
            "email": email,
            "fullName": profile.full_name or "",
            "role": profile.role,
        },
        account={
            "id": org.id,
            "name": org.name,
            "plan": "pro",
        }
    )


@router.get("/cloud-providers")
def list_cloud_providers() -> list[CloudProviderItem]:
    """
    Return list of supported cloud providers.
    """
    return [
        CloudProviderItem(
            id="aws",
            name="Amazon Web Services",
            icon="aws",
            description="AWS billing and resource analysis",
        ),
        CloudProviderItem(
            id="gcp",
            name="Google Cloud Platform",
            icon="gcp",
            description="GCP billing and resource analysis",
        ),
        CloudProviderItem(
            id="azure",
            name="Microsoft Azure",
            icon="azure",
            description="Azure billing and resource analysis",
        ),
    ]


PROVIDER_LABELS = {
    "aws": "Amazon Web Services",
    "gcp": "Google Cloud Platform",
    "azure": "Microsoft Azure",
}


@router.get("/connected-accounts")
def list_connected_accounts(
    org_id: str = Query(..., description="Organization ID"),
    db: Session = Depends(get_db),
) -> list[dict]:
    org = db.query(models.Organization).filter_by(id=org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    rows = db.query(models.CloudProvider).filter_by(org_id=org_id).all()
    return [
        {
            "id": row.id,
            "name": PROVIDER_LABELS.get(row.provider_type, row.provider_type.upper()),
            "provider": row.provider_type.upper(),
            "lastSync": row.last_sync.isoformat() if row.last_sync else None,
            "status": "connected" if row.is_connected else "pending",
        }
        for row in rows
    ]


@router.post("/onboarding/connect")
def connect_cloud_provider(
    provider: str = Query(..., description="Cloud provider type (aws/gcp/azure)"),
    org_id: str = Query(..., description="Organization ID"),
    payload: ConnectCloudRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    actor: models.UserProfile = Depends(get_remediation_actor),
) -> dict:
    """Verify and store AWS execution credentials using authenticated org scope."""
    ensure_org_access(actor, org_id)
    if actor.role != "admin":
        raise HTTPException(status_code=403, detail="Only an organization admin can connect cloud credentials")
    provider = provider.lower()
    if provider != "aws":
        raise HTTPException(status_code=501, detail="Live connection verification currently supports AWS only")
    org = db.query(models.Organization).filter_by(id=org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    credentials = payload.credentials if payload else {}
    access_key_id = credentials.get("access_key_id")
    secret_access_key = credentials.get("secret_access_key")
    region = credentials.get("region")
    if not isinstance(access_key_id, str) or not re.fullmatch(r"(?:AKIA|ASIA)[0-9A-Z]{16}", access_key_id):
        raise HTTPException(status_code=422, detail="A valid AWS access key ID is required")
    if not isinstance(secret_access_key, str) or len(secret_access_key) < 32:
        raise HTTPException(status_code=422, detail="A valid AWS secret access key is required")
    if not isinstance(region, str) or not re.fullmatch(r"[a-z]{2}(?:-gov)?-[a-z]+-\d", region):
        raise HTTPException(status_code=422, detail="A valid AWS region is required")

    try:
        import boto3

        aws_session = boto3.Session(
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            aws_session_token=credentials.get("session_token"),
            region_name=region,
        )
        identity = aws_session.client("sts").get_caller_identity()
        encrypted_credentials = encrypt_cloud_credentials({
            "access_key_id": access_key_id,
            "secret_access_key": secret_access_key,
            "session_token": credentials.get("session_token"),
            "region": region,
            "account_id": identity["Account"],
        })
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail="AWS credentials could not be verified for the selected region") from exc

    existing = db.query(models.CloudProvider).filter_by(
        org_id=org_id,
        provider_type=provider
    ).first()

    now = datetime.datetime.utcnow()
    if existing:
        existing.is_connected = True
        existing.last_sync = now
        existing.credentials_encrypted = encrypted_credentials
    else:
        cp = models.CloudProvider(
            org_id=org_id,
            provider_type=provider,
            credentials_encrypted=encrypted_credentials,
            is_connected=True,
            last_sync=now,
        )
        db.add(cp)

    db.commit()

    return {
        "ok": True,
        "provider": provider,
        "status": "connected",
        "account_id": identity["Account"],
        "region": region,
        "message": "AWS identity verified and credentials encrypted. Billing ingestion is not configured by this connection flow.",
    }


@router.get("/onboarding/iam-policy")
def get_iam_policy(provider: str = Query("aws", description="Cloud provider (aws/gcp/azure)")) -> dict:
    """
    Generate IAM policy for cloud provider based on provider type.
    """
    policies = {
        "aws": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "ce:GetCostAndUsage",
                        "ce:DescribeCostCategoryDefinition",
                        "ec2:DescribeInstances",
                    ],
                    "Resource": "*"
                },
                {
                    "Effect": "Allow",
                    "Action": ["ec2:StopInstances"],
                    "Resource": "arn:aws:ec2:*:*:instance/*",
                    "Condition": {
                        "StringEquals": {"ec2:ResourceTag/EcoPulseAutomation": "enabled"}
                    }
                },
            ]
        },
        "gcp": {
            "version": "1",
            "etag": "BwWZa7lW9tI=",
            "bindings": [
                {
                    "role": "roles/monitoring.viewer",
                    "members": ["serviceAccount:ecopulse@PROJECT_ID.iam.gserviceaccount.com"]
                },
                {
                    "role": "roles/compute.viewer",
                    "members": ["serviceAccount:ecopulse@PROJECT_ID.iam.gserviceaccount.com"]
                },
                {
                    "role": "roles/billing.viewer",
                    "members": ["serviceAccount:ecopulse@PROJECT_ID.iam.gserviceaccount.com"]
                }
            ]
        },
        "azure": {
            "assignableScopes": [
                "/subscriptions/{subscriptionId}"
            ],
            "permissions": [
                {
                    "actions": [
                        "Microsoft.Compute/virtualMachines/read",
                        "Microsoft.Storage/storageAccounts/read",
                        "Microsoft.Sql/servers/read",
                        "Microsoft.CostManagement/query/action",
                        "Microsoft.ResourceGraph/resources/read",
                    ],
                    "notActions": []
                }
            ]
        }
    }
    
    return policies.get(provider, {})


@router.get("/onboarding/access-checklist")
def get_access_checklist(
    provider: str = Query("aws", description="Cloud provider (aws/gcp/azure)")
) -> list[AccessChecklistItem]:
    """
    Return required permissions checklist for a cloud provider.
    """
    checklists = {
        "aws": [
            AccessChecklistItem(item="Cost Explorer access", required=True, status="pending"),
            AccessChecklistItem(item="EC2 read access", required=True, status="pending"),
            AccessChecklistItem(item="S3 read access", required=True, status="pending"),
            AccessChecklistItem(item="RDS read access", required=False, status="pending"),
            AccessChecklistItem(item="Lambda read access", required=False, status="pending"),
        ],
        "gcp": [
            AccessChecklistItem(item="Monitoring Viewer role", required=True, status="pending"),
            AccessChecklistItem(item="Compute Viewer role", required=True, status="pending"),
            AccessChecklistItem(item="Billing Viewer role", required=True, status="pending"),
        ],
        "azure": [
            AccessChecklistItem(item="Virtual Machine Reader", required=True, status="pending"),
            AccessChecklistItem(item="Storage Account Reader", required=True, status="pending"),
            AccessChecklistItem(item="Cost Management Reader", required=True, status="pending"),
        ]
    }
    
    return checklists.get(provider, [])
