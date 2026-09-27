"""Seed the configured local database with correlated synthetic EcoPulse data."""

from backend.db import models
from backend.db.database import SessionLocal
from backend.services.pipeline_service import run_organization_pipeline

ORG_ID = "local-test-org"
USER_ID = "local-test-user"


def main() -> None:
    db = SessionLocal()
    try:
        org = db.query(models.Organization).filter_by(id=ORG_ID).first()
        if org is None:
            org = models.Organization(id=ORG_ID, name="EcoPulse Local Test")
            db.add(org)
            db.flush()

        profile = db.query(models.UserProfile).filter_by(id=USER_ID).first()
        if profile is None:
            db.add(models.UserProfile(id=USER_ID, org_id=ORG_ID, role="admin"))
        else:
            profile.org_id = ORG_ID
            profile.role = "admin"
        db.commit()

        result = run_organization_pipeline(db, ORG_ID, collect=True)
        totals = {
            "billing": db.query(models.BillingRecord).filter_by(org_id=ORG_ID).count(),
            "infrastructure": db.query(models.InfrastructureMetric).filter_by(org_id=ORG_ID).count(),
            "gpu": db.query(models.GPUMetric).filter_by(org_id=ORG_ID).count(),
            "k8s": db.query(models.K8sMetric).filter_by(org_id=ORG_ID).count(),
            "logs": db.query(models.OperationalLog).filter_by(org_id=ORG_ID).count(),
            "waste": db.query(models.WasteItem).filter_by(org_id=ORG_ID).count(),
            "recommendations": db.query(models.Recommendation).filter_by(org_id=ORG_ID).count(),
            "alerts": db.query(models.Alert).filter_by(org_id=ORG_ID).count(),
        }
        print({"org_id": ORG_ID, "pipeline": result, "database_totals": totals})
    finally:
        db.close()


if __name__ == "__main__":
    main()
