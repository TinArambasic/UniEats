"""Add organization model and tenant scoping.

Revision ID: 0008_add_organizations_multi_tenant
Revises: 0007_make_student_fields_nullable
Create Date: 2026-04-30 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0008_add_organizations_multi_tenant"
down_revision = "0007_make_student_fields_nullable"
branch_labels = None
depends_on = None


def _insert_default_organization() -> int:
    bind = op.get_bind()
    insert_stmt = sa.text(
        "INSERT INTO organizations (name, is_active) " "VALUES (:name, :is_active)"
    )
    bind.execute(
        insert_stmt,
        {
            "name": "Default Organization",
            "is_active": True,
        },
    )
    return bind.execute(
        sa.text("SELECT id FROM organizations WHERE name = :name"),
        {"name": "Default Organization"},
    ).scalar_one()


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_organizations_name", "organizations", ["name"])
    op.create_index("ix_organizations_created_at", "organizations", ["created_at"])

    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("organization_id", sa.Integer(), nullable=True))

    with op.batch_alter_table("menu_items") as batch:
        batch.add_column(sa.Column("organization_id", sa.Integer(), nullable=True))

    with op.batch_alter_table("orders") as batch:
        batch.add_column(sa.Column("organization_id", sa.Integer(), nullable=True))

    default_org_id = _insert_default_organization()
    op.execute(
        sa.text(
            "UPDATE users SET organization_id = :org_id "
            "WHERE organization_id IS NULL"
        ).bindparams(org_id=default_org_id)
    )
    op.execute(
        sa.text(
            "UPDATE menu_items SET organization_id = :org_id "
            "WHERE organization_id IS NULL"
        ).bindparams(org_id=default_org_id)
    )
    op.execute(
        sa.text(
            "UPDATE orders SET organization_id = :org_id "
            "WHERE organization_id IS NULL"
        ).bindparams(org_id=default_org_id)
    )

    with op.batch_alter_table("users") as batch:
        batch.alter_column("organization_id", nullable=False)
        batch.create_foreign_key(
            "fk_users_organization_id_organizations",
            "organizations",
            ["organization_id"],
            ["id"],
        )
    op.create_index("ix_users_organization_id", "users", ["organization_id"])

    with op.batch_alter_table("menu_items") as batch:
        batch.alter_column("organization_id", nullable=False)
        batch.create_foreign_key(
            "fk_menu_items_organization_id_organizations",
            "organizations",
            ["organization_id"],
            ["id"],
        )
    op.create_index("ix_menu_items_organization_id", "menu_items", ["organization_id"])

    with op.batch_alter_table("orders") as batch:
        batch.alter_column("organization_id", nullable=False)
        batch.create_foreign_key(
            "fk_orders_organization_id_organizations",
            "organizations",
            ["organization_id"],
            ["id"],
        )
    op.create_index("ix_orders_organization_id", "orders", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_orders_organization_id", table_name="orders")
    with op.batch_alter_table("orders") as batch:
        batch.drop_constraint(
            "fk_orders_organization_id_organizations", type_="foreignkey"
        )
        batch.drop_column("organization_id")

    op.drop_index("ix_menu_items_organization_id", table_name="menu_items")
    with op.batch_alter_table("menu_items") as batch:
        batch.drop_constraint(
            "fk_menu_items_organization_id_organizations",
            type_="foreignkey",
        )
        batch.drop_column("organization_id")

    op.drop_index("ix_users_organization_id", table_name="users")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint(
            "fk_users_organization_id_organizations", type_="foreignkey"
        )
        batch.drop_column("organization_id")

    op.drop_index("ix_organizations_created_at", table_name="organizations")
    op.drop_index("ix_organizations_name", table_name="organizations")
    op.drop_table("organizations")
