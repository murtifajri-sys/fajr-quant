"""Use BIGINT for stock shares outstanding.

Revision ID: 20260713_0002
Revises: 20260713_0001
Create Date: 2026-07-13
"""
from alembic import op
import sqlalchemy as sa


revision = "20260713_0002"
down_revision = "20260713_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "stocks",
        "shares_outstanding",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "stocks",
        "shares_outstanding",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
    )
