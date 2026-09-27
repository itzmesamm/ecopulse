import json
from io import BytesIO

from backend.db import models
from backend.genai import rag_pipeline
from backend.genai.embeddings import retrieve_relevant_logs_lexical
from backend.services import recommendation_service


def test_synthetic_idle_log_is_retrieved_for_finding(db_session):
    org = models.Organization(name="Synthetic RAG test")
    db_session.add(org)
    db_session.flush()
    db_session.add_all([
        models.OperationalLog(
            org_id=org.id,
            source="gpu",
            message="gpu-demo-7 idle with no workload; VRAM use 400MB",
            severity="WARNING",
        ),
        models.OperationalLog(
            org_id=org.id,
            source="billing",
            message="daily charge increased for unrelated resource",
            severity="INFO",
        ),
    ])
    db_session.commit()

    results = retrieve_relevant_logs_lexical(
        db_session,
        org.id,
        "GPU gpu-demo-7 low utilization",
        top_k=3,
    )

    assert results
    assert "gpu-demo-7" in results[0]["content"]


def test_synthetic_finding_is_sent_to_ollama_with_logs_and_savings_bound(db_session, monkeypatch):
    org = models.Organization(name="Synthetic agent test")
    db_session.add(org)
    db_session.flush()
    db_session.add(models.OperationalLog(
        org_id=org.id,
        source="gpu",
        message="gpu-demo-7 idle with no workload",
        severity="WARNING",
    ))
    db_session.commit()

    prompt_received = {}

    class OllamaResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({
                "response": json.dumps({
                    "explanation": "Synthetic telemetry and its matching idle log corroborate the finding.",
                    "dollar_savings": 999.0,
                    "confidence": 0.91,
                    "suggested_action": "Review the sandbox GPU and schedule it to stop when unused.",
                })
            }).encode()

    def fake_urlopen(request, timeout):
        prompt_received["body"] = json.loads(request.data.decode())
        return OllamaResponse()

    monkeypatch.setenv("EMBEDDINGS_ENABLED", "false")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test")
    monkeypatch.setattr(rag_pipeline.request, "urlopen", fake_urlopen)

    result = rag_pipeline.generate_recommendation(
        db_session,
        org.id,
        {
            "source_type": "gpu",
            "resource_id": "gpu-demo-7",
            "waste_type": "gpu_idle",
            "severity_score": 0.9,
            "estimated_monthly_waste_usd": 40.0,
            "details": "GPU gpu-demo-7 is idle and drawing power.",
        },
    )

    assert result is not None
    assert result["dollar_savings"] == 40.0
    assert result["confidence"] == 0.91
    assert "gpu-demo-7 idle with no workload" in prompt_received["body"]["prompt"]


def test_one_failed_llm_call_keeps_successful_synthetic_recommendation(monkeypatch):
    calls = iter([
        {
            "explanation": "The correlated synthetic signals confirm idle GPU capacity.",
            "dollar_savings": 25,
            "confidence": 0.88,
            "suggested_action": "Review and schedule the idle sandbox GPU.",
            "agent_provider": "ollama",
        },
        None,
    ])
    monkeypatch.setattr(recommendation_service, "generate_recommendation", lambda *args, **kwargs: next(calls))
    context = [
        {"source_type":"gpu","resource_id":"gpu-demo-7","service":"GPU","environment":"sandbox","waste_type":"gpu_idle","severity_score":0.9,"estimated_monthly_waste_usd":25,"details":"GPU idle"},
        {"source_type":"waste","resource_id":"i-demo-8","service":"ec2","environment":"sandbox","waste_type":"low_utilization","severity_score":0.8,"estimated_monthly_waste_usd":30,"details":"Low usage"},
    ]

    results = recommendation_service._generate_ai_recommendations(None, "test-org", context)

    assert results is not None
    assert len(results) == 2
    assert results[0]["summary"].startswith("The correlated synthetic signals")
    assert json.loads(results[0]["context_json"])["agent_provider"] == "ollama"
    assert json.loads(results[1]["context_json"])["agent_provider"] == "deterministic_fallback"