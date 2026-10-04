import json
from io import BytesIO

from fastapi.testclient import TestClient

from backend.api import assistant
from backend.db import models
from backend.genai import rag_pipeline
from backend.main import app


def test_assistant_skips_embedding_work_when_disabled(db_session, monkeypatch):
    org = models.Organization(name="Fast Chat Test")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)

    monkeypatch.setenv("EMBEDDINGS_ENABLED", "false")
    monkeypatch.setattr(
        assistant,
        "embed_and_store_logs",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("embedding called")),
    )
    monkeypatch.setattr(
        assistant,
        "retrieve_relevant_logs",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("retrieval called")),
    )
    monkeypatch.setattr(assistant, "_call_ollama", lambda prompt, model_name: "Fast answer.")

    response = TestClient(app).post(
        "/assistant/chat",
        json={"org_id": org.id, "question": "What waste should I review?"},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "Fast answer."


def test_recommendation_skips_embedding_and_keeps_model_warm(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_ENABLED", "false")
    monkeypatch.setenv("OLLAMA_KEEP_ALIVE", "10m")
    monkeypatch.setattr(
        rag_pipeline,
        "embed_and_store_logs",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("embedding called")),
    )
    monkeypatch.setattr(
        rag_pipeline,
        "retrieve_relevant_logs",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("retrieval called")),
    )

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return json.dumps({
                "response": json.dumps({
                    "explanation": "Model answer.",
                    "dollar_savings": 25,
                    "confidence": 0.8,
                    "suggested_action": "Review sizing.",
                })
            }).encode()

    def fake_urlopen(req, timeout):
        payload = json.loads(req.data)
        assert payload["keep_alive"] == "10m"
        assert "suggested_action" in payload["format"]["required"]
        return FakeResponse()

    monkeypatch.setattr(rag_pipeline.request, "urlopen", fake_urlopen)

    result = rag_pipeline.generate_recommendation(
        db=None,
        org_id="org-1",
        waste_finding={"resource_id": "resource-1", "details": "Low usage"},
    )

    assert result["explanation"] == "Model answer."