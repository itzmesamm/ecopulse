import json
import os
from typing import Any, Dict, Optional
from urllib import error, request

from sqlalchemy.orm import Session

from backend.genai.embeddings import (
    embed_and_store_logs,
    retrieve_relevant_logs,
    retrieve_relevant_logs_lexical,
)
from backend.genai.prompt_templates import build_recommendation_prompt, parse_recommendation_response


def generate_recommendation(
    db: Session,
    org_id: str,
    waste_finding: Dict[str, Any],
    model: Optional[Any] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve relevant logs and ask Ollama for one grounded recommendation."""
    embeddings_available = os.getenv("EMBEDDINGS_ENABLED", "true").lower() == "true"
    if embeddings_available:
        try:
            embed_and_store_logs(db, org_id, model=model)
        except Exception:
            # The recommendation can still be generated without retrieved logs.
            embeddings_available = False

    query = waste_finding.get("details") or waste_finding.get("resource_id") or waste_finding.get("waste_type") or "cloud waste"
    try:
        if embeddings_available:
            context_logs = retrieve_relevant_logs(db, org_id, query=query, top_k=3, model=model)
        else:
            context_logs = retrieve_relevant_logs_lexical(db, org_id, query=query, top_k=3)
    except Exception:
        context_logs = []

    prompt = build_recommendation_prompt(waste_finding, context_logs)
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model_name = os.getenv("OLLAMA_MODEL", "llama3")
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.2},
    }

    try:
        timeout_seconds = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
        req = request.Request(
            f"{base_url.rstrip('/')}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
        raw_response = body.get("response")
        if not isinstance(raw_response, str):
            return None
        result = parse_recommendation_response(raw_response)
        evidence_limit = max(0.0, float(waste_finding.get("estimated_monthly_waste_usd") or 0.0))
        result["dollar_savings"] = min(result["dollar_savings"], evidence_limit)
        result["agent_provider"] = "ollama"
        if result["suggested_action"] == "manual_review":
            result["confidence"] = min(result["confidence"], 0.3)
        return result
    except (error.URLError, TimeoutError, ValueError, TypeError, json.JSONDecodeError):
        return None
