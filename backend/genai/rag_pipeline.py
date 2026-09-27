import json
import os
from typing import Any, Dict, Optional
from urllib import error, request

from sqlalchemy.orm import Session

from backend.genai.embeddings import embed_and_store_logs, retrieve_relevant_logs
from backend.genai.prompt_templates import build_recommendation_prompt, parse_recommendation_response


def generate_recommendation(
    db: Session,
    org_id: str,
    waste_finding: Dict[str, Any],
    model: Optional[Any] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve relevant logs and ask Ollama for one grounded recommendation."""
    try:
        embed_and_store_logs(db, org_id, model=model)
    except (RuntimeError, ValueError, ImportError):
        # The recommendation can still be generated without retrieved logs.
        pass

    try:
        context_logs = retrieve_relevant_logs(
            db,
            org_id,
            query=(waste_finding.get("details") or waste_finding.get("waste_type") or "cloud waste"),
            top_k=3,
            model=model,
        )
    except (RuntimeError, ValueError, ImportError):
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
        req = request.Request(
            f"{base_url.rstrip('/')}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=60) as response:
            body = json.loads(response.read().decode("utf-8"))
        raw_response = body.get("response")
        if not isinstance(raw_response, str):
            return None
        return parse_recommendation_response(raw_response)
    except (error.URLError, TimeoutError, ValueError, TypeError, json.JSONDecodeError):
        return None
