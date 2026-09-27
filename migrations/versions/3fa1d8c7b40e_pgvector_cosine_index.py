"""add pgvector cosine index for log retrieval

Revision ID: 3fa1d8c7b40e
Revises: 9bd197d186d8
"""
from typing import Sequence, Union

from alembic import op


revision: str = "3fa1d8c7b40e"
down_revision: Union[str, None] = "9bd197d186d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    has_pgvector = connection.dialect.name == "postgresql" and bool(
        connection.exec_driver_sql("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')").scalar()
    )
    if has_pgvector:
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_log_embeddings_embedding_cosine "
            "ON log_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_log_embeddings_embedding_cosine")