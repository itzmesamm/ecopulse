import json
import math
from typing import Any, List, Optional, Sequence

from sqlalchemy.orm import Session

from backend.db import models

_MODEL_NAME = "all-MiniLM-L6-v2"
_model = None


def _get_model():
    """Load the local Hugging Face embedder only when the pipeline is used."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required for log embeddings. "
                "Install dependencies with: pip install -r requirements.txt"
            ) from exc
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def embed_text(text: str, model: Optional[Any] = None) -> List[float]:
    """Create a 384-dimensional embedding for text."""
    encoder = model or _get_model()
    vector = encoder.encode(text)
    values = vector.tolist() if hasattr(vector, "tolist") else list(vector)
    if len(values) != 384:
        raise ValueError(f"Expected 384 embedding dimensions, got {len(values)}")
    return [float(value) for value in values]


def embed_and_store_logs(
    db: Session,
    org_id: str,
    model: Optional[Any] = None,
) -> int:
    """Embed each org log and upsert one vector row per operational log."""
    logs = db.query(models.OperationalLog).filter(models.OperationalLog.org_id == org_id).all()
    stored = 0
    for log in logs:
        existing = db.query(models.LogEmbedding).filter(
            models.LogEmbedding.org_id == org_id,
            models.LogEmbedding.source_ref == log.id,
        ).first()
        vector = embed_text(log.message, model=model)
        if existing:
            existing.content = log.message
            existing.embedding = vector
        else:
            db.add(models.LogEmbedding(
                org_id=org_id,
                content=log.message,
                embedding=vector,
                source_ref=log.id,
            ))
        stored += 1
    db.commit()
    return stored


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def retrieve_relevant_logs(
    db: Session,
    org_id: str,
    query: str,
    top_k: int = 3,
    model: Optional[Any] = None,
) -> List[dict[str, Any]]:
    """Retrieve org-scoped logs by cosine similarity.

    Python scoring keeps local SQLite tests working. Supabase deployments can
    use the matching pgvector SQL function in infra/genai_pgvector.sql.
    """
    query_vector = embed_text(query, model=model)
    rows = db.query(models.LogEmbedding).filter(models.LogEmbedding.org_id == org_id).all()
    ranked = []
    for row in rows:
        embedding = row.embedding
        if isinstance(embedding, str):
            embedding = json.loads(embedding)
        ranked.append({
            "content": row.content,
            "source_ref": row.source_ref,
            "similarity": _cosine_similarity(query_vector, embedding),
        })
    ranked.sort(key=lambda item: item["similarity"], reverse=True)
    return ranked[:top_k]
