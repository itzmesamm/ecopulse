from types import SimpleNamespace
from unittest.mock import MagicMock

from backend.genai.embeddings import retrieve_relevant_logs


class FixedEncoder:
    def encode(self, text):
        return [1.0] + [0.0] * 383


def test_postgres_retrieval_uses_org_scoped_vector_search():
    db = MagicMock()
    db.bind.dialect.name = "postgresql"
    db.execute.return_value.mappings.return_value.all.return_value = [
        {"content": "gpu idle", "source_ref": "log-1", "similarity": 0.95}
    ]

    results = retrieve_relevant_logs(db, "tenant-a", "why gpu idle", top_k=2, model=FixedEncoder())

    assert results[0]["content"] == "gpu idle"
    sql = str(db.execute.call_args.args[0])
    params = db.execute.call_args.args[1]
    assert "embedding <=>" in sql
    assert "org_id = :org_id" in sql
    assert params["org_id"] == "tenant-a"
    assert params["top_k"] == 2