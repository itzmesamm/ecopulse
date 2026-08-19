import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.db import models
from backend.genai.rag_pipeline import generate_recommendation
from backend.greenops.carbon_calc import (
    estimate_carbon_savings_kg_for_gpu_finding,
    estimate_carbon_savings_kg_for_waste_item,
)


def _build_recommendation_context(
    db: Session,
    org_id: str,
    service: Optional[str] = None,
    environment: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    # Build a mixed context list (waste + GPU optimizations) so the GenAI
    # can produce recommendations from multiple FinOps/GreenOps signals.
    query = db.query(models.WasteItem).filter(models.WasteItem.org_id == org_id)
    if service:
        query = query.filter(models.WasteItem.service == service)
    if environment:
        query = query.filter(models.WasteItem.environment == environment)

    items = query.order_by(models.WasteItem.severity_score.desc()).limit(limit).all()
    context = []
    for item in items:
        context.append(
            {
                "source_type": "waste",
                "waste_finding_id": item.id,
                "resource_id": item.resource_id,
                "service": item.service,
                "environment": item.environment,
                "waste_type": item.waste_type,
                "severity_score": round(float(item.severity_score), 3),
                "estimated_monthly_waste_usd": round(float(item.estimated_monthly_waste_usd), 2),
                "details": item.details,
                "region": item.region,
            }
        )

    # Add top GPU findings as additional context (roadmap-style multi-signal).
    gpu_query = db.query(models.GPUOptimizationFinding).filter(models.GPUOptimizationFinding.org_id == org_id)
    if environment:
        gpu_query = gpu_query.filter(models.GPUOptimizationFinding.environment == environment)
    gpu_items = gpu_query.order_by(models.GPUOptimizationFinding.severity_score.desc()).limit(max(0, limit // 2)).all()

    for g in gpu_items:
        context.append(
            {
                "source_type": "gpu",
                "resource_id": g.gpu_id,  # used as Recommendation.resource_id
                "service": "GPU",
                "environment": g.environment,
                "waste_type": "gpu_idle",
                "severity_score": round(float(g.severity_score or 0.0), 3),
                "estimated_monthly_waste_usd": round(float(g.estimated_monthly_waste_usd or 0.0), 2),
                "details": g.details,
                "region": None,
            }
        )

    return context


def _fallback_recommendations(context: List[Dict[str, Any]], org_id: str) -> List[Dict[str, Any]]:
    recommendations = []
    for item in context:
        resource_id = item.get("resource_id") or "resource"
        service = item.get("service") or "unknown-service"
        env = item.get("environment") or "unknown-environment"
        severity = float(item.get("severity_score") or 0.0)
        waste_usd = float(item.get("estimated_monthly_waste_usd") or 0.0)
        source_type = item.get("source_type") or "waste"

        if source_type == "gpu":
            title = f"Shut down idle GPU ({resource_id})"
            summary = (
                f"GPU {resource_id} in {env} appears underutilized. "
                "A shutdown / reschedule can reduce unnecessary compute spend."
            )
            action = "Schedule shutdown or reschedule idle GPU jobs to reduce idle compute."
            rationale = "CPU/GPU telemetry indicates low utilization while power draw is still incurred."
            priority = "high" if severity >= 0.7 else "medium"
        elif item.get("waste_type") == "low_utilization":
            title = f"Right-size idle {service} resource"
            summary = f"{resource_id} in {env} shows low utilization and may be idle for a large portion of the month."
            action = "Scale the resource down or schedule shutdown during idle periods to reduce unnecessary spend."
            rationale = "The workload is underutilized while still incurring monthly cost."
            priority = "high" if severity >= 0.7 else "medium"
        else:
            title = f"Optimize oversize {service} workload"
            summary = f"{resource_id} in {env} has a high cost-per-hour profile and low usage, indicating potential overprovisioning."
            action = "Review instance size, storage profile, and workload scheduling to reduce waste without impacting performance."
            rationale = "The cost profile suggests the workload is oversized relative to the actual demand."
            priority = "high" if severity >= 0.8 else "medium"

        recommendations.append(
            {
                "org_id": org_id,
                "waste_finding_id": item.get("waste_finding_id"),
                "resource_id": resource_id,
                "service": service,
                "environment": env,
                "source_type": source_type,
                "recommendation_type": "optimization",
                "title": title,
                "summary": summary,
                "action": action,
                "rationale": rationale,
                "priority": priority,
                "confidence_score": round(min(0.99, 0.6 + (severity * 0.4)), 2),
                "estimated_savings_usd": round(waste_usd, 2),
                "explanation": summary,
                "dollar_savings": round(waste_usd, 2),
                "suggested_action": action,
                "status": "pending",
                "context_json": json.dumps(item),
            }
        )

    return recommendations


def _generate_ai_recommendations(
    db: Session,
    org_id: str,
    context: List[Dict[str, Any]],
) -> Optional[List[Dict[str, Any]]]:
    if not context:
        return []

    recommendations = []
    for waste_finding in context:
        result = generate_recommendation(db, org_id, waste_finding)
        if result is None:
            return None
        source_type = waste_finding.get("source_type") or "waste"
        recommendations.append(
            {
                **waste_finding,
                "source_type": source_type,
                "recommendation_type": "optimization",
                "title": f"Review {waste_finding.get('resource_id', 'resource')} optimization",
                "summary": result["explanation"],
                "action": result["suggested_action"],
                "rationale": result["explanation"],
                "priority": "high" if waste_finding["severity_score"] >= 0.7 else "medium",
                "confidence_score": result["confidence"],
                "estimated_savings_usd": result["dollar_savings"],
                "explanation": result["explanation"],
                "dollar_savings": result["dollar_savings"],
                "suggested_action": result["suggested_action"],
                "context_json": json.dumps(waste_finding),
            }
        )
    return recommendations


def generate_recommendations_for_org(
    db: Session,
    org_id: str,
    service: Optional[str] = None,
    environment: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    context = _build_recommendation_context(db, org_id, service=service, environment=environment, limit=limit)
    if not context:
        return []

    ai_recommendations = _generate_ai_recommendations(db, org_id, context)
    if ai_recommendations:
        for item in ai_recommendations:
            item.setdefault("org_id", org_id)
            item.setdefault("source_type", "waste")
            item.setdefault("recommendation_type", "optimization")
            item.setdefault("priority", "medium")
            item.setdefault("confidence_score", 0.7)
            item.setdefault("estimated_savings_usd", 0.0)
            item.setdefault("context_json", json.dumps(context))
        return ai_recommendations

    return _fallback_recommendations(context, org_id)


def save_recommendations(db: Session, org_id: str, recommendations: List[Dict[str, Any]]) -> List[models.Recommendation]:
    saved: List[models.Recommendation] = []
    for item in recommendations:
        # Compute carbon impact if it wasn’t generated by the LLM contract.
        carbon_savings_kg = item.get("carbon_savings_kg")
        waste_finding_id = item.get("waste_finding_id")
        source_type = item.get("source_type", "waste")
        resource_id = item.get("resource_id")

        if carbon_savings_kg is None and waste_finding_id:
            try:
                carbon_savings_kg = estimate_carbon_savings_kg_for_waste_item(
                    db=db,
                    org_id=org_id,
                    waste_item_id=waste_finding_id,
                )
            except Exception:
                # Keep integrations resilient; carbon can be computed later when data improves.
                carbon_savings_kg = None

        # GPU-based carbon estimate (if waste_finding_id wasn’t present)
        if carbon_savings_kg is None and source_type == "gpu" and resource_id:
            try:
                carbon_savings_kg = estimate_carbon_savings_kg_for_gpu_finding(
                    db=db,
                    org_id=org_id,
                    gpu_id=resource_id,
                )
            except Exception:
                carbon_savings_kg = None

        record = models.Recommendation(
            org_id=org_id,
            resource_id=item.get("resource_id"),
            service=item.get("service"),
            environment=item.get("environment"),
            source_type=item.get("source_type", "waste"),
            recommendation_type=item.get("recommendation_type", "optimization"),
            title=item.get("title") or "Optimization Recommendation",
            summary=item.get("summary") or "No summary provided.",
            action=item.get("action") or "Review resource usage and cost profile.",
            rationale=item.get("rationale") or "Generated from waste analysis.",
            priority=item.get("priority", "medium"),
            confidence_score=float(item.get("confidence_score") or 0.0),
            estimated_savings_usd=float(item.get("estimated_savings_usd") or 0.0),
            context_json=item.get("context_json") or json.dumps(item),
            waste_finding_id=item.get("waste_finding_id"),
            explanation=item.get("explanation") or item.get("summary"),
            dollar_savings=float(item.get("dollar_savings") or item.get("estimated_savings_usd") or 0.0),
            carbon_savings_kg=carbon_savings_kg,
            suggested_action=item.get("suggested_action") or item.get("action"),
            status=item.get("status", "pending"),
        )
        db.add(record)
        saved.append(record)
    db.commit()
    for record in saved:
        db.refresh(record)
    return saved
