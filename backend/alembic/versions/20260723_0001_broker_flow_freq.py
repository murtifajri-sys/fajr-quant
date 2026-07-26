"""add broker flow frequency columns

Revision ID: 20260723_0001
Revises: 20260722_0001
Create Date: 2026-07-23 20:05:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "20260723_0001"
down_revision = "20260722_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("broker_flows", sa.Column("buy_freq", sa.Integer(), nullable=True))
    op.add_column("broker_flows", sa.Column("sell_freq", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("broker_flows", "sell_freq")
    op.drop_column("broker_flows", "buy_freq")
