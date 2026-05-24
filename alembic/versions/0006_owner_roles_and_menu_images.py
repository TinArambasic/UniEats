"""Add owner role support and menu item images.

Revision ID: 0006_owner_roles_and_menu_images
Revises: 0005_add_indexes
Create Date: 2026-04-30 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0006_owner_roles_and_menu_images"
down_revision = "0005_add_indexes"
branch_labels = None
depends_on = None


def _upgrade_user_role_enum() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'owner'")


def upgrade() -> None:
    _upgrade_user_role_enum()
    bind = op.get_bind()

    with op.batch_alter_table("users") as batch:
        batch.alter_column(
            "student_card_number",
            existing_type=sa.String(length=32),
            nullable=True,
        )

    if bind.dialect.name != "postgresql":
        with op.batch_alter_table("users") as batch:
            batch.alter_column(
                "role",
                existing_type=sa.Enum("student", "admin", name="userrole"),
                type_=sa.Enum("student", "admin", "owner", name="userrole"),
                nullable=False,
            )

    with op.batch_alter_table("menu_items") as batch:
        batch.add_column(sa.Column("image_url", sa.String(length=512), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()

    with op.batch_alter_table("menu_items") as batch:
        batch.drop_column("image_url")

    op.execute("UPDATE users SET role='admin' WHERE role='owner'")
    op.execute(
        "UPDATE users SET student_card_number = 'legacy-' || id "
        "WHERE student_card_number IS NULL"
    )

    if bind.dialect.name != "postgresql":
        with op.batch_alter_table("users") as batch:
            batch.alter_column(
                "role",
                existing_type=sa.Enum("student", "admin", "owner", name="userrole"),
                type_=sa.Enum("student", "admin", name="userrole"),
                nullable=False,
            )

    with op.batch_alter_table("users") as batch:
        batch.alter_column(
            "student_card_number",
            existing_type=sa.String(length=32),
            nullable=False,
        )
