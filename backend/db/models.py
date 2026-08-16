"""
ORM tables for EcoPulse — Org/Auth foundation + Layer 1 (raw ingestion).

Organization    -> a company/tenant using EcoPulse (multi-tenant root)
UserProfile     -> app-level profile for a Supabase Auth user; links a login to an org + role
BillingRecord   -> raw Layer-1 billing ingestion (per org)
GPUMetric       -> raw Layer-1 GPU telemetry ingestion (per org)
K8sMetric       -> raw Layer-1 Kubernetes metrics ingestion (per org)
OperationalLog  -> raw Layer-1 operational log ingestion (per org)

Layer 2+ tables (waste_items, recommendations, remediation_actions, forecasts,
anomalies, log_embeddings, alerts) will be added when we build those layers.
"""
import datetime
import uuid
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.db.database import Base


def _uuid():
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Org & Auth
# ---------------------------------------------------------------------------

class Organization(Base):
    """A company/tenant. Every business table hangs off org_id."""
    __tablename__ = "organizations"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class UserProfile(Base):
    """
    App-level profile for a Supabase Auth user.

    id is NOT auto-generated — it must equal the id of the corresponding row
    in Supabase's own `auth.users` table (managed entirely by Supabase Auth
    in a separate schema, so we don't declare a SQLAlchemy ForeignKey to it —
    we just store the matching UUID and rely on the signup flow to set it).
    """
    __tablename__ = "user_profiles"

    id = Column(String, primary_key=True)  # == supabase auth.users.id
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    full_name = Column(String, nullable=True)
    role = Column(String, default="viewer")  # admin | approver | viewer
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    organization = relationship("Organization")


# ---------------------------------------------------------------------------
# Layer 1 — raw ingestion (per-org)
# ---------------------------------------------------------------------------

class BillingRecord(Base):
    __tablename__ = "billing_records"

    id = Column(String, primary_key=True, default=_uuid)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    resource_id = Column(String, nullable=False)
    service = Column(String, nullable=True)
    region = Column(String, nullable=True)
    account = Column(String, nullable=True)
    environment = Column(String, default="production")
    cost = Column(Float, nullable=True)
    usage_hours = Column(Float, nullable=True)
    recorded_at = Column(DateTime, default=datetime.datetime.utcnow)


class GPUMetric(Base):
    __tablename__ = "gpu_metrics"

    id = Column(String, primary_key=True, default=_uuid)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    gpu_id = Column(String, nullable=False)
    account = Column(String, nullable=True)
    environment = Column(String, default="production")
    utilization_pct = Column(Float, nullable=True)
    vram_used_mb = Column(Float, nullable=True)
    power_watts = Column(Float, nullable=True)
    temp_c = Column(Float, nullable=True)
    recorded_at = Column(DateTime, default=datetime.datetime.utcnow)


class K8sMetric(Base):
    __tablename__ = "k8s_metrics"

    id = Column(String, primary_key=True, default=_uuid)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    pod_name = Column(String, nullable=False)
    namespace = Column(String, nullable=True)
    cpu_usage = Column(Float, nullable=True)
    memory_usage = Column(Float, nullable=True)
    recorded_at = Column(DateTime, default=datetime.datetime.utcnow)


class OperationalLog(Base):
    __tablename__ = "operational_logs"

    id = Column(String, primary_key=True, default=_uuid)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    source = Column(String, nullable=True)
    message = Column(Text, nullable=False)
    severity = Column(String, default="INFO")
    recorded_at = Column(DateTime, default=datetime.datetime.utcnow)
