"""add ipo major holder snapshots

Revision ID: 20260726_0001
Revises: 20260723_0001
Create Date: 2026-07-26 22:30:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "20260726_0001"
down_revision = "20260723_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ipo_major_holder_snapshots",
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("holder_count", sa.Integer(), nullable=False),
        sa.Column("top_holder_name", sa.String(length=255), nullable=True),
        sa.Column("top_holder_pct", sa.Float(), nullable=True),
        sa.Column("total_major_holder_pct", sa.Float(), nullable=True),
        sa.Column("free_float_estimate_pct", sa.Float(), nullable=True),
        sa.Column("holder_risk_label", sa.String(length=48), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ticker"], ["stocks.ticker"]),
        sa.PrimaryKeyConstraint("ticker", "as_of_date"),
    )
    op.create_index("ix_ipo_major_holder_ticker_fetched", "ipo_major_holder_snapshots", ["ticker", "fetched_at"], unique=False)
    op.create_index("ix_ipo_major_holder_label", "ipo_major_holder_snapshots", ["holder_risk_label"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ipo_major_holder_label", table_name="ipo_major_holder_snapshots")
    op.drop_index("ix_ipo_major_holder_ticker_fetched", table_name="ipo_major_holder_snapshots")
    op.drop_table("ipo_major_holder_snapshots")
