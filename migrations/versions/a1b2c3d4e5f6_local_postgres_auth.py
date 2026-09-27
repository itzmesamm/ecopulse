"""Replace Supabase Auth with local Postgres email/password auth."""

from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f6"
down_revision = "3fa1d8c7b40e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_profiles", sa.Column("email", sa.String(), nullable=True))
    op.add_column("user_profiles", sa.Column("password_hash", sa.String(), nullable=True))
    op.create_unique_constraint("uq_user_profiles_email", "user_profiles", ["email"])


def downgrade() -> None:
    op.drop_constraint("uq_user_profiles_email", "user_profiles", type_="unique")
    op.drop_column("user_profiles", "password_hash")
    op.drop_column("user_profiles", "email")
