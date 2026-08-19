"""
Auth endpoints — org signup + login, backed by Supabase Auth.

  POST /auth/signup  -> creates a Supabase Auth user, a new Organization,
                         and a UserProfile (role="admin") linking them.
                         This is how a NEW company/tenant onboards.
  POST /auth/login   -> verifies credentials via Supabase Auth, returns the
                         session (access_token) plus the caller's org_id/role.
"""
<<<<<<< Updated upstream
from fastapi import APIRouter, HTTPException, Depends
=======
from fastapi import APIRouter, HTTPException, Depends, Query, Body
>>>>>>> Stashed changes
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db.supabase_client import get_supabase
from backend.db import models
from backend.ingestion.persist import ingest_and_persist
from backend.analysis.waste_analyzer import WasteAnalyzer, persist_waste_items

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
<<<<<<< Updated upstream
=======


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
            "email": user_id,  # Would come from Supabase in production
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

    if existing:
        existing.is_connected = True
        existing.last_sync = datetime.utcnow()
        existing.credentials_encrypted = json.dumps(credentials) if credentials else None
    else:
        cp = models.CloudProvider(
            org_id=org_id,
            provider_type=provider,
            credentials_encrypted=json.dumps(credentials) if credentials else None,
            is_connected=True,
            last_sync=datetime.utcnow(),
        )
        db.add(cp)

    db.commit()

    ingest_result = ingest_and_persist(db, org_id)
    analyzer = WasteAnalyzer()
    waste_results = analyzer.analyze_records(db, org_id)
    items_persisted = persist_waste_items(db, org_id, waste_results)

    return {
        "ok": True,
        "provider": provider,
        "status": "connected",
        "message": f"Successfully connected {provider} to organization {org_id}",
        "ingested": ingest_result,
        "waste_items_identified": items_persisted,
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
>>>>>>> Stashed changes
