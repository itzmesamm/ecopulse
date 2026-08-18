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
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

from backend.db.database import Base, engine, get_db
from backend.api.auth import router as auth_router
from backend.api.waste_analytics import router as waste_analytics_router
from backend.api.forecasting import router as forecasting_router
from backend.ingestion.persist import ingest_and_persist

Base.metadata.create_all(bind=engine)

app = FastAPI(title="EcoPulse", description="AI-powered FinOps and GreenOps platform", version="0.1.0")
app.include_router(auth_router)
app.include_router(waste_analytics_router)
app.include_router(forecasting_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ingest")
def ingest(org_id: str, db: Session = Depends(get_db)):
    """
    Layer 1: pulls synthetic billing/GPU/K8s/log data and persists it to
    billing_records / gpu_metrics / k8s_metrics / operational_logs, scoped
    to org_id. Create an org first via POST /auth/signup.
    """
    return ingest_and_persist(db, org_id)
