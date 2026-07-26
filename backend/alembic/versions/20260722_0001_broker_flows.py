"""add broker_flows table

Revision ID: 20260722_0001
Revises: 3aaf3ac27691
Create Date: 2026-07-22 13:45:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "20260722_0001"
down_revision = "3aaf3ac27691"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "broker_flows",
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("broker", sa.String(length=16), nullable=False),
        sa.Column("buy_value", sa.Float(), nullable=False),
        sa.Column("sell_value", sa.Float(), nullable=False),
        sa.Column("net_value", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ticker"], ["stocks.ticker"]),
        sa.PrimaryKeyConstraint("ticker", "date", "broker"),
    )
    op.create_index("ix_broker_flow_ticker_date", "broker_flows", ["ticker", "date"], unique=False)
    op.create_index(
        "ix_broker_flow_ticker_broker_date",
        "broker_flows",
        ["ticker", "broker", "date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_broker_flow_ticker_broker_date", table_name="broker_flows")
    op.drop_index("ix_broker_flow_ticker_date", table_name="broker_flows")
    op.drop_table("broker_flows")
