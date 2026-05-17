"""Add rich frontend-facing fields to buildings.

Frontend ждёт name/district/object_type как стабильные поля плюс
большую rich-форму (контакты, инженерные системы, факторы). Чтобы не
делать ~25 колонок, добавляем 3 типизированных + details JSONB.

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("buildings", sa.Column("name", sa.Text(), nullable=True))
    op.add_column("buildings", sa.Column("district", sa.Text(), nullable=True))
    op.add_column("buildings", sa.Column("object_type", sa.Text(), nullable=True))
    op.add_column(
        "buildings",
        sa.Column("details", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.create_index("idx_buildings_district", "buildings", ["district"])


def downgrade() -> None:
    op.drop_index("idx_buildings_district", table_name="buildings")
    op.drop_column("buildings", "details")
    op.drop_column("buildings", "object_type")
    op.drop_column("buildings", "district")
    op.drop_column("buildings", "name")
