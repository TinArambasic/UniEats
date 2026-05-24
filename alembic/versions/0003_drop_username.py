"""Drop username from users.

Revision ID: 0003_drop_username
Revises: 0002_profile_nutrition
Create Date: 2026-04-01 00:00:02.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0003_drop_username"
down_revision = "0002_profile_nutrition"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_username")
        batch.drop_column("username")
        batch.alter_column(
            "student_card_number",
            existing_type=sa.String(length=32),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("username", sa.String(length=50), nullable=True))
        batch.create_index("ix_users_username", ["username"], unique=False)
        batch.alter_column(
            "student_card_number",
            existing_type=sa.String(length=32),
            nullable=True,
        )
