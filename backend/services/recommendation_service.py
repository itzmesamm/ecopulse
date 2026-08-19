import json
import os
from typing import Any, Dict, List, Optional
from urllib import request, error

from sqlalchemy.orm import Session

from backend.db import models


def _build_recommendation_context(
    db: Session,
    org_id: str,
    service: Optional[str] = None,
    environment: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
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
    return context


def _fallback_recommendations(context: List[Dict[str, Any]], org_id: str) -> List[Dict[str, Any]]:
    recommendations = []
    for item in context:
        resource_id = item.get("resource_id") or "resource"
        service = item.get("service") or "unknown-service"
        env = item.get("environment") or "unknown-environment"
        severity = float(item.get("severity_score") or 0.0)
        waste_usd = float(item.get("estimated_monthly_waste_usd") or 0.0)

        if item.get("waste_type") == "low_utilization":
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
                "resource_id": resource_id,
                "service": service,
                "environment": env,
                "source_type": "waste",
                "recommendation_type": "optimization",
                "title": title,
                "summary": summary,
                "action": action,
                "rationale": rationale,
                "priority": priority,
                "confidence_score": round(min(0.99, 0.6 + (severity * 0.4)), 2),
                "estimated_savings_usd": round(waste_usd, 2),
                "context_json": json.dumps(item),
            }
        )

    return recommendations


def _generate_ai_recommendations(context: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    if not context:
        return []

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model_name = os.getenv("OLLAMA_MODEL", "llama3.1")
    if not model_name:
        return None

    prompt = (
        "You are a FinOps and GreenOps advisor. "
        "Based on the waste findings below, generate strictly valid JSON only. "
        "Return a JSON object with exactly one top-level key named 'recommendations'. "
        "The value must be a list of up to 3 recommendations. "
        "Each recommendation must include exactly these fields: "
        "title, summary, action, rationale, priority, confidence_score, estimated_savings_usd, "
        "resource_id, service, environment, source_type, recommendation_type. "
        "Use only values that are realistic for cloud cost optimization. "
        "Confidence score must be a float between 0.0 and 1.0. "
        "Estimated savings must be a non-negative number. "
        "Do not include markdown or extra explanation.\n\n"
        f"Waste findings:\n{json.dumps(context, indent=2)}"
    )

    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.2},
    }

    try:
        url = f"{base_url.rstrip('/')}/api/generate"
        req = request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=60) as response:
            body = response.read().decode("utf-8")
        result = json.loads(body)
        raw_text = (result.get("response") or "").strip()
        if not raw_text:
            return None

        parsed = json.loads(raw_text)
        recommendations = parsed.get("recommendations")
        if not isinstance(recommendations, list):
            return None
        return recommendations
    except (error.URLError, ValueError, TypeError, json.JSONDecodeError):
        return None


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

    ai_recommendations = _generate_ai_recommendations(context)
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
        )
        db.add(record)
        saved.append(record)
    db.commit()
    for record in saved:
        db.refresh(record)
    return saved
