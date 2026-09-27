"""
EcoPulse backend entrypoint.

Currently wires up:
  - Org/Auth (Supabase Auth-backed signup/login)
  - Layer 1: raw data ingestion + persistence, scoped per-org
  - Layer 2: Cost & Waste Analytics (identify optimization opportunities)
  - Layer 3: Cost Forecasting (predict future costs)

Run with: uvicorn backend.main:app --reload
Docs at:  http://localhost:8000/docs
"""
import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.api.auth import router as auth_router
from backend.api.waste_analytics import router as waste_analytics_router
from backend.api.forecasting import router as forecasting_router
from backend.api.recommendations import router as recommendation_router
from backend.api.anomalies import router as anomalies_router
from backend.api.gpu_optimizer import router as gpu_optimizer_router
from backend.api.cost_grouping import router as cost_grouping_router
from backend.api.remediation import router as remediation_router
from backend.api.alerts import router as alerts_router
from backend.api.assistant import router as assistant_router
from backend.api.greenops import router as greenops_router
from backend.api.security import OrgAuthenticationMiddleware
from backend.api.pipeline import router as pipeline_router
from backend.ingestion.persist import ingest_and_persist

app = FastAPI(title="EcoPulse", description="AI-powered FinOps and GreenOps platform", version="0.1.0")

# CORS configuration
cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,"
        "http://localhost:5174,"
        "http://localhost:3000,"
        "http://127.0.0.1:5173,"
        "http://127.0.0.1:5174,"
        "http://127.0.0.1:3000",
    ).split(",")
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(OrgAuthenticationMiddleware)
app.include_router(auth_router)
app.include_router(waste_analytics_router)
app.include_router(forecasting_router)
app.include_router(recommendation_router)
app.include_router(anomalies_router)
app.include_router(gpu_optimizer_router)
app.include_router(cost_grouping_router)
app.include_router(remediation_router)
app.include_router(alerts_router)
app.include_router(assistant_router)
app.include_router(greenops_router)
app.include_router(pipeline_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ingest")
def ingest(org_id: str, db: Session = Depends(get_db)):
    """
    Layer 1: collects configured billing, infrastructure, GPU, Kubernetes,
    and operational log sources and persists them scoped to org_id.
    """
    return ingest_and_persist(db, org_id)
