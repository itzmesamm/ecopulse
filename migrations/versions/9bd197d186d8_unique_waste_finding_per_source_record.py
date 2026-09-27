"""add ingestion tables for databases adopted from the pre-Alembic schema

Revision ID: 9bd197d186d8
Revises: ce298c799493
Create Date: 2026-09-27 12:25:08.782609
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = '9bd197d186d8'
down_revision: Union[str, None] = 'ce298c799493'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing_tables = set(inspect(op.get_bind()).get_table_names())
    if 'infrastructure_metrics' not in existing_tables:
        op.create_table(
            'infrastructure_metrics',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('org_id', sa.String(), nullable=False),
            sa.Column('host_id', sa.String(), nullable=False),
            sa.Column('cpu_pct', sa.Float(), nullable=True),
            sa.Column('memory_pct', sa.Float(), nullable=True),
            sa.Column('disk_pct', sa.Float(), nullable=True),
            sa.Column('network_receive_bytes_per_second', sa.Float(), nullable=True),
            sa.Column('network_transmit_bytes_per_second', sa.Float(), nullable=True),
            sa.Column('recorded_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['org_id'], ['organizations.id']),
            sa.PrimaryKeyConstraint('id'),
        )
    if 'ingestion_records' not in existing_tables:
        op.create_table(
            'ingestion_records',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('org_id', sa.String(), nullable=False),
            sa.Column('source', sa.String(), nullable=False),
            sa.Column('source_key', sa.String(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['org_id'], ['organizations.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('org_id', 'source', 'source_key', name='uq_ingestion_event'),
        )


def downgrade() -> None:
    op.drop_table('ingestion_records')
    op.drop_table('infrastructure_metrics')
