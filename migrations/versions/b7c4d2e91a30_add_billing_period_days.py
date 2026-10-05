"""add billing period length

Revision ID: b7c4d2e91a30
Revises: e46e60ad0594
Create Date: 2026-10-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7c4d2e91a30"
down_revision: Union[str, None] = "e46e60ad0594"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("billing_records")}
    if "period_days" not in columns:
        op.add_column(
            "billing_records",
            sa.Column("period_days", sa.Integer(), server_default=sa.text("30"), nullable=False),
        )


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("billing_records")}
    if "period_days" in columns:
        op.drop_column("billing_records", "period_days")