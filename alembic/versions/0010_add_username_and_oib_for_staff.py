"""Add username and OIB fields for staff authentication

Revision ID: 0010
Revises: 0009_multi_org_profiles_and_hours
Create Date: 2024-01-01

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: str | None = "0009_multi_org_profiles_and_hours"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add new columns for staff authentication
    # username is nullable because existing users may not have one
    op.add_column("users", sa.Column("username", sa.String(length=50), nullable=True))
    op.add_column("users", sa.Column("oib", sa.String(length=11), nullable=True))

    # Make email nullable for staff users (using batch mode for SQLite compatibility)
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("email", existing_type=sa.String(), nullable=True)

    # Create unique constraints for username and oib
    with op.batch_alter_table("users") as batch_op:
        batch_op.create_unique_constraint("uq_users_username", ["username"])
        batch_op.create_unique_constraint("uq_users_oib", ["oib"])

    # Create indexes for faster lookups
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=False)
    op.create_index(op.f("ix_users_oib"), "users", ["oib"], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f("ix_users_oib"), table_name="users")
    op.drop_index(op.f("ix_users_username"), table_name="users")

    # Drop unique constraints
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("uq_users_oib", type_="unique")
        batch_op.drop_constraint("uq_users_username", type_="unique")

    # Remove columns
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("oib")
        batch_op.drop_column("username")
