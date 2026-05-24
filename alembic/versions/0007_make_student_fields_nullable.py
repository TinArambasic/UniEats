"""Ensure student fields are nullable for role-based users.

Revision ID: 0007_make_student_fields_nullable
Revises: 0006_owner_roles_and_menu_images
Create Date: 2026-04-30 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0007_make_student_fields_nullable"
down_revision = "0006_owner_roles_and_menu_images"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.alter_column(
            "student_card_number",
            existing_type=sa.String(length=32),
            nullable=True,
        )
        batch.alter_column(
            "student_esi",
            existing_type=sa.String(length=32),
            nullable=True,
        )


def downgrade() -> None:
    op.execute(
        "UPDATE users SET student_card_number = 'legacy-' || id "
        "WHERE student_card_number IS NULL"
    )
    op.execute(
        "UPDATE users SET student_esi = 'legacy-esi-' || id "
        "WHERE student_esi IS NULL"
    )
    with op.batch_alter_table("users") as batch:
        batch.alter_column(
            "student_card_number",
            existing_type=sa.String(length=32),
            nullable=False,
        )
        batch.alter_column(
            "student_esi",
            existing_type=sa.String(length=32),
            nullable=False,
        )
