"""Add user profile and nutrition fields.

Revision ID: 0002_profile_nutrition
Revises: 0001_initial
Create Date: 2026-04-01 00:00:01.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_profile_nutrition"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("first_name", sa.String(length=50), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.String(length=50), nullable=True))
    op.add_column("users", sa.Column("subsidy_remaining", sa.Float(), nullable=True))

    op.add_column("menu_items", sa.Column("calories_kcal", sa.Float(), nullable=True))
    op.add_column("menu_items", sa.Column("protein_g", sa.Float(), nullable=True))
    op.add_column("menu_items", sa.Column("carbs_g", sa.Float(), nullable=True))
    op.add_column("menu_items", sa.Column("fat_g", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("menu_items", "fat_g")
    op.drop_column("menu_items", "carbs_g")
    op.drop_column("menu_items", "protein_g")
    op.drop_column("menu_items", "calories_kcal")

    op.drop_column("users", "subsidy_remaining")
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
