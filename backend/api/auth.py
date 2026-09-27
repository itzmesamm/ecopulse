"""
Auth endpoints — org signup + login, backed by local Postgres.

  POST /auth/signup  -> creates Organization + UserProfile (admin) with
                         email/password stored in Postgres; returns access token.
  POST /auth/login   -> verifies email/password against Postgres and returns
                         a signed access token plus org_id/role.
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Body
import datetime
import json
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db import models
from backend.db.local_auth import create_access_token, hash_password, verify_password
from backend.services.pipeline_service import run_organization_pipeline

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
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
    email = payload.email.strip().lower()
    existing = db.query(models.UserProfile).filter(models.UserProfile.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    org = models.Organization(name=payload.org_name.strip() or "New Organization")
    db.add(org)
    db.flush()

    profile = models.UserProfile(
        org_id=org.id,
        email=email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role="admin",
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    return {
        "user_id": profile.id,
        "org_id": org.id,
        "role": "admin",
        "access_token": create_access_token(profile.id),
    }


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Verifies local Postgres credentials and returns the session + org context."""
    email = payload.email.strip().lower()
    profile = db.query(models.UserProfile).filter(models.UserProfile.email == email).first()
    if not profile or not verify_password(payload.password, profile.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return {
        "access_token": create_access_token(profile.id),
        "user_id": profile.id,
        "org_id": profile.org_id,
        "role": profile.role,
    }


@router.post("/dev-login")
def dev_login(db: Session = Depends(get_db)):
    """
    Local/demo session for synthetic prototypes without a password signup.
    Disabled automatically when APP_ENV=production.
    """
    import os

    if os.getenv("APP_ENV", "development").lower() == "production":
        raise HTTPException(status_code=404, detail="Not found")

    token = os.getenv("DEV_AUTH_TOKEN") or "local-only-test-token"
    user_id = os.getenv("DEV_AUTH_USER_ID") or "local-test-user"
    org_id = os.getenv("DEV_AUTH_ORG_ID") or "local-test-org"

    org = db.query(models.Organization).filter_by(id=org_id).first()
    if org is None:
        org = models.Organization(id=org_id, name="EcoPulse Local Demo")
        db.add(org)
        db.flush()

    profile = db.query(models.UserProfile).filter_by(id=user_id).first()
    if profile is None:
        db.add(
            models.UserProfile(
                id=user_id,
                org_id=org.id,
                email="demo@ecopulse.local",
                full_name="Local Demo Admin",
                role="admin",
            )
        )
    else:
        profile.org_id = org.id
        profile.role = "admin"
        if not profile.full_name:
            profile.full_name = "Local Demo Admin"
        if not profile.email:
            profile.email = "demo@ecopulse.local"
    db.commit()

    return {
        "access_token": token,
        "user_id": user_id,
        "org_id": org.id,
        "role": "admin",
        "demo": True,
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

    return CurrentUserResponse(
        user={
            "id": profile.id,
            "email": profile.email or "",
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
) -> dict:
    """
    Store cloud provider credentials, ingest synthetic data, and run waste analysis.
    """
    org = db.query(models.Organization).filter_by(id=org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    credentials = payload.credentials if payload else None

    existing = db.query(models.CloudProvider).filter_by(
        org_id=org_id,
        provider_type=provider
    ).first()

    now = datetime.datetime.utcnow()
    if existing:
        existing.is_connected = True
        existing.last_sync = now
        existing.credentials_encrypted = json.dumps(credentials) if credentials else None
    else:
        cp = models.CloudProvider(
            org_id=org_id,
            provider_type=provider,
            credentials_encrypted=json.dumps(credentials) if credentials else None,
            is_connected=True,
            last_sync=now,
        )
        db.add(cp)

    db.commit()

    has_billing = db.query(models.BillingRecord).filter_by(org_id=org_id).first()
    try:
        pipeline_result = run_organization_pipeline(
            db, org_id, collect=has_billing is None
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "ok": True,
        "provider": provider,
        "status": "connected",
        "message": f"Successfully connected {provider} to organization {org_id}",
        "pipeline": pipeline_result,
        "waste_items_identified": pipeline_result.get("waste_findings", 0),
        "recommendations_generated": pipeline_result.get("recommendations", 0),
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
                        "ec2:DescribeVolumes",
                        "ec2:DescribeNetworkInterfaces",
                        "rds:DescribeDBInstances",
                        "s3:ListAllMyBuckets",
                        "s3:GetBucketLocation",
                        "lambda:ListFunctions",
                    ],
                    "Resource": "*"
                }
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
