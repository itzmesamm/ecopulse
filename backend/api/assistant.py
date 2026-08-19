from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.db import models
from backend.db.database import get_db
from backend.genai.embeddings import embed_and_store_logs, retrieve_relevant_logs
from backend.forecasting.forecaster import forecast_costs_safe

router = APIRouter(prefix="/assistant", tags=["assistant"])


class ChatHistoryItem(BaseModel):
    q: str
    a: str


class ChatRequest(BaseModel):
    org_id: str
    question: str
    history: Optional[list[ChatHistoryItem]] = None
    top_k_logs: int = Field(default=3, ge=1, le=10)


def _classify(question: str) -> str:
    q = question.lower()
    if any(w in q for w in ["forecast", "predict", "future", "next month", "tomorrow", "cost trend"]):
        return "forecasts"
    if any(w in q for w in ["carbon", "co2", "emission", "greenops", "kg"]):
        return "greenops"
    if any(w in q for w in ["gpu", "vram", "utilization", "power"]):
        return "gpu"
    if any(w in q for w in ["anomaly", "outlier", "score", "deviate"]):
        return "anomalies"
    return "waste"


def _call_ollama(prompt: str, *, model_name: str) -> str:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    timeout_seconds = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
    max_tokens = int(os.getenv("OLLAMA_MAX_TOKENS", "64"))
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": max_tokens},
    }

    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
        raw_response = body.get("response")
        if not isinstance(raw_response, str):
            raise ValueError("Ollama response missing 'response' field")
        return raw_response
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Ollama call failed: {exc}") from exc


@router.post("/chat")
def chat(payload: ChatRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    org = db.query(models.Organization).filter(models.Organization.id == payload.org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    route = _classify(payload.question)

    # Ensure logs are embedded (best effort).
    log_embedding_count = (
        db.query(models.LogEmbedding)
        .filter(models.LogEmbedding.org_id == payload.org_id)
        .count()
    )
    if log_embedding_count == 0:
        try:
            embed_and_store_logs(db, payload.org_id)
        except Exception:
            # Assistant can still answer from structured DB context.
            pass

    try:
        relevant_logs = retrieve_relevant_logs(
            db,
            payload.org_id,
            query=payload.question,
            top_k=payload.top_k_logs,
        )
    except Exception:
        relevant_logs = []

    # Structured DB context per route
    if route == "waste":
        waste_items = (
            db.query(models.WasteItem)
            .filter(models.WasteItem.org_id == payload.org_id)
            .order_by(models.WasteItem.severity_score.desc())
            .limit(6)
            .all()
        )
        context = {
            "waste_items": [
                {
                    "id": w.id,
                    "resource_id": w.resource_id,
                    "service": w.service,
                    "environment": w.environment,
                    "waste_type": w.waste_type,
                    "severity_score": float(w.severity_score),
                    "estimated_monthly_waste_usd": float(w.estimated_monthly_waste_usd),
                    "details": w.details,
                }
                for w in waste_items
            ],
        }
    elif route == "forecasts":
        result, error = forecast_costs_safe(db, payload.org_id, forecast_days=30)
        if error:
            context = {"forecast_error": error.message}
        else:
            context = {
                "forecast_period_days": len(result.forecasts),
                "total_forecasted_cost_usd": sum(float(f.forecasted_cost_usd or 0.0) for f in result.forecasts),
                "top_days": [
                    {
                        "date": f.forecast_date.isoformat(),
                        "forecasted_cost_usd": float(f.forecasted_cost_usd),
                        "ci_lower": float(f.confidence_lower_bound),
                        "ci_upper": float(f.confidence_upper_bound),
                    }
                    for f in result.forecasts[:5]
                ],
            }
    elif route == "anomalies":
        rows = (
            db.query(models.AnomalyFinding)
            .filter(models.AnomalyFinding.org_id == payload.org_id)
            .order_by(models.AnomalyFinding.severity_score.desc())
            .limit(6)
            .all()
        )
        context = {
            "anomalies": [
                {
                    "resource_id": r.resource_id,
                    "service": r.service,
                    "environment": r.environment,
                    "anomaly_score": float(r.anomaly_score),
                    "severity_score": float(r.severity_score),
                    "details": r.details,
                }
                for r in rows
            ]
        }
    elif route == "gpu":
        rows = (
            db.query(models.GPUOptimizationFinding)
            .filter(models.GPUOptimizationFinding.org_id == payload.org_id)
            .order_by(models.GPUOptimizationFinding.severity_score.desc())
            .limit(6)
            .all()
        )
        context = {
            "gpu_optimizations": [
                {
                    "gpu_id": r.gpu_id,
                    "environment": r.environment,
                    "utilization_pct": float(r.utilization_pct),
                    "power_watts": float(r.power_watts),
                    "severity_score": float(r.severity_score),
                    "estimated_monthly_waste_usd": float(r.estimated_monthly_waste_usd),
                    "details": r.details,
                }
                for r in rows
            ]
        }
    else:  # greenops
        executed = (
            db.query(models.Recommendation)
            .filter(models.Recommendation.org_id == payload.org_id, models.Recommendation.status == "executed")
            .order_by(models.Recommendation.created_at.desc())
            .limit(6)
            .all()
        )
        total_carbon = sum(float(r.carbon_savings_kg or 0.0) for r in executed)
        total_usd = sum(float(r.dollar_savings or 0.0) for r in executed)
        context = {
            "executed_recommendations": [
                {
                    "id": r.id,
                    "resource_id": r.resource_id,
                    "environment": r.environment,
                    "dollar_savings": float(r.dollar_savings or 0.0),
                    "carbon_savings_kg": float(r.carbon_savings_kg or 0.0),
                    "title": r.title,
                }
                for r in executed
            ],
            "totals": {"total_carbon_savings_kg": total_carbon, "total_dollar_savings_usd": total_usd},
        }

    history_text = ""
    if payload.history:
        # Keep short to avoid prompt bloat.
        last = payload.history[-3:]
        history_text = "\n".join([f"Q: {h.q}\nA: {h.a}" for h in last])

    system_prompt = (
        "You are EcoPulse's assistant for FinOps and GreenOps. "
        "Answer ONLY using the provided context. "
        "If the context does not contain the answer, say so honestly. "
        "Keep the answer concise (max ~8 lines)."
    )

    prompt = (
        f"{system_prompt}\n\n"
        f"Route: {route}\n"
        f"Conversation history (last turns):\n{history_text or 'None'}\n\n"
        f"Structured context (JSON):\n{json.dumps(context)[:6000]}\n\n"
        f"Relevant operational logs:\n{json.dumps(relevant_logs)[:4000]}\n\n"
        f"User question: {payload.question}\n\n"
        "Answer:"
    )

    model_name = os.getenv("OLLAMA_MODEL", "llama3.1")
    try:
        answer = _call_ollama(prompt, model_name=model_name)
    except RuntimeError as exc:
        # Return a safe fallback answer.
        answer = f"Could not call Ollama: {exc}"

    return {"route": route, "answer": answer}

