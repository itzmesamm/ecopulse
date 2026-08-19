import json
from typing import Any, Dict


SYSTEM_PROMPT = """You are a FinOps and GreenOps assistant.
ONLY use the provided waste finding and retrieved context.
Never invent numbers, resources, causes, or savings not present in the context.
Always return one JSON object with exactly these keys:
explanation, dollar_savings, confidence, suggested_action.
confidence must be a number from 0 to 1.
dollar_savings must be a non-negative number.
Return JSON only, with no markdown or extra text."""


def build_recommendation_prompt(waste_finding: Dict[str, Any], context_logs: list[dict[str, Any]]) -> str:
    context_text = "\n".join(
        f"- {entry['content']} (similarity={entry['similarity']:.3f})"
        for entry in context_logs
    ) or "- No relevant operational logs were found."
    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"Retrieved operational context:\n{context_text}\n\n"
        f"Waste finding:\n{json.dumps(waste_finding, sort_keys=True)}\n\n"
        "Respond ONLY with the required JSON object."
    )


def parse_recommendation_response(raw_llm_response: str) -> Dict[str, Any]:
    """Parse and normalize the synopsis output contract."""
    try:
        parsed = json.loads(raw_llm_response)
        if not isinstance(parsed, dict):
            raise ValueError("response must be a JSON object")
        explanation = str(parsed.get("explanation") or "")
        action = str(parsed.get("suggested_action") or "manual_review")
        savings = max(0.0, float(parsed.get("dollar_savings") or 0.0))
        confidence = min(1.0, max(0.0, float(parsed.get("confidence") or 0.0)))
        if not explanation:
            raise ValueError("explanation is required")
        return {
            "explanation": explanation,
            "dollar_savings": savings,
            "confidence": confidence,
            "suggested_action": action,
        }
    except (json.JSONDecodeError, TypeError, ValueError):
        return {
            "explanation": raw_llm_response.strip() or "The model returned no explanation.",
            "dollar_savings": 0.0,
            "confidence": 0.3,
            "suggested_action": "manual_review",
        }
