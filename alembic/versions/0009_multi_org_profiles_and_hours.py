"""Multi-organization memberships, profile images, and organization metadata.

Revision ID: 0009_multi_org_profiles_and_hours
Revises: 0008_add_organizations_multi_tenant
Create Date: 2026-04-30 00:00:01.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0009_multi_org_profiles_and_hours"
down_revision = "0008_add_organizations_multi_tenant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("organizations") as batch:
        batch.add_column(sa.Column("address", sa.String(length=200), nullable=True))
        batch.add_column(sa.Column("city", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("phone", sa.String(length=40), nullable=True))
        batch.add_column(sa.Column("latitude", sa.Float(), nullable=True))
        batch.add_column(sa.Column("longitude", sa.Float(), nullable=True))
    op.create_index("ix_organizations_city", "organizations", ["city"])

    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("profile_image_url", sa.String(length=512), nullable=True)
        )

    op.create_table(
        "user_organizations",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("user_id", "organization_id"),
    )
    op.create_index(
        "ix_user_organizations_created_at",
        "user_organizations",
        ["created_at"],
    )

    op.create_table(
        "user_favorite_organizations",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("user_id", "organization_id"),
    )
    op.create_index(
        "ix_user_favorite_organizations_created_at",
        "user_favorite_organizations",
        ["created_at"],
    )

    op.create_table(
        "organization_working_hours",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("is_closed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("open_time", sa.String(length=5), nullable=True),
        sa.Column("close_time", sa.String(length=5), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.UniqueConstraint(
            "organization_id",
            "day_of_week",
            name="uq_org_working_hours_org_day",
        ),
    )
    op.create_index(
        "ix_organization_working_hours_organization_id",
        "organization_working_hours",
        ["organization_id"],
    )
    op.create_index(
        "ix_organization_working_hours_day_of_week",
        "organization_working_hours",
        ["day_of_week"],
    )

    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT OR IGNORE INTO user_organizations (user_id, organization_id) "
            "SELECT id, organization_id FROM users WHERE organization_id IS NOT NULL"
        )
    )

    org_ids = [
        row[0]
        for row in bind.execute(sa.text("SELECT id FROM organizations")).fetchall()
    ]
    for org_id in org_ids:
        for day in range(7):
            bind.execute(
                sa.text(
                    "INSERT OR IGNORE INTO organization_working_hours "
                    "(organization_id, day_of_week, is_closed, open_time, close_time) "
                    "VALUES (:organization_id, :day_of_week, :is_closed, :open_time, :close_time)"
                ),
                {
                    "organization_id": org_id,
                    "day_of_week": day,
                    "is_closed": False,
                    "open_time": "08:00",
                    "close_time": "20:00",
                },
            )


def downgrade() -> None:
    op.drop_index(
        "ix_organization_working_hours_day_of_week",
        table_name="organization_working_hours",
    )
    op.drop_index(
        "ix_organization_working_hours_organization_id",
        table_name="organization_working_hours",
    )
    op.drop_table("organization_working_hours")

    op.drop_index(
        "ix_user_favorite_organizations_created_at",
        table_name="user_favorite_organizations",
    )
    op.drop_table("user_favorite_organizations")

    op.drop_index(
        "ix_user_organizations_created_at",
        table_name="user_organizations",
    )
    op.drop_table("user_organizations")

    with op.batch_alter_table("users") as batch:
        batch.drop_column("profile_image_url")

    op.drop_index("ix_organizations_city", table_name="organizations")
    with op.batch_alter_table("organizations") as batch:
        batch.drop_column("longitude")
        batch.drop_column("latitude")
        batch.drop_column("phone")
        batch.drop_column("city")
        batch.drop_column("address")
