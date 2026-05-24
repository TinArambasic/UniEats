"""Add meal ratings table

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-07

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "meal_ratings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("menu_item_id", sa.Integer(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "rating >= 1 AND rating <= 5", name="ck_meal_ratings_rating"
        ),
        sa.ForeignKeyConstraint(["menu_item_id"], ["menu_items.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "menu_item_id",
            name="uq_meal_ratings_user_menu_item",
        ),
    )
    op.create_index(
        op.f("ix_meal_ratings_user_id"), "meal_ratings", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_meal_ratings_menu_item_id"),
        "meal_ratings",
        ["menu_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_meal_ratings_created_at"),
        "meal_ratings",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_meal_ratings_created_at"), table_name="meal_ratings")
    op.drop_index(op.f("ix_meal_ratings_menu_item_id"), table_name="meal_ratings")
    op.drop_index(op.f("ix_meal_ratings_user_id"), table_name="meal_ratings")
    op.drop_table("meal_ratings")
