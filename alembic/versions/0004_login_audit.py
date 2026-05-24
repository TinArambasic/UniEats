"""Add login audit table.

Revision ID: 0004_login_audit
Revises: 0003_drop_username
Create Date: 2026-04-01 00:00:03.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0004_login_audit"
down_revision = "0003_drop_username"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "login_audits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_card_number", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("reason", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index(
        "ix_login_audits_student_card_number",
        "login_audits",
        ["student_card_number"],
    )


def downgrade() -> None:
    op.drop_index("ix_login_audits_student_card_number", table_name="login_audits")
    op.drop_table("login_audits")
