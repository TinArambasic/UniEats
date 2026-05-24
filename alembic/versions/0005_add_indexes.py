"""Add indexes for foreign keys and audit timestamps.

Revision ID: 0005_add_indexes
Revises: 0004_login_audit
Create Date: 2026-04-01 00:00:04.000000
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0005_add_indexes"
down_revision = "0004_login_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_orders_user_id", "orders", ["user_id"])
    op.create_index("ix_orders_created_at", "orders", ["created_at"])
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])
    op.create_index("ix_order_items_menu_item_id", "order_items", ["menu_item_id"])
    op.create_index("ix_login_audits_created_at", "login_audits", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_login_audits_created_at", table_name="login_audits")
    op.drop_index("ix_order_items_menu_item_id", table_name="order_items")
    op.drop_index("ix_order_items_order_id", table_name="order_items")
    op.drop_index("ix_orders_created_at", table_name="orders")
    op.drop_index("ix_orders_user_id", table_name="orders")
