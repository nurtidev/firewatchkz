"""Create building_features table

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "building_features",
        sa.Column(
            "id",
            sa.Text(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()::text"),
        ),
        sa.Column(
            "building_id",
            sa.Text(),
            sa.ForeignKey("buildings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "city_id",
            sa.Text(),
            sa.ForeignKey("cities.id"),
            nullable=False,
        ),
        sa.Column(
            "feature_date",
            sa.Date(),
            nullable=False,
            server_default=sa.text("CURRENT_DATE"),
        ),
        sa.Column("nearest_hydrant_m", sa.Numeric(), nullable=True),
        sa.Column("nearest_station_m", sa.Numeric(), nullable=True),
        sa.Column("incidents_500m_3y", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("incidents_on_building_3y", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("building_density_500m", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("age_years", sa.Integer(), nullable=True),
        sa.Column("population_estimate", sa.Numeric(), nullable=True),
        sa.Column("days_since_last_incident", sa.Integer(), nullable=True),
        sa.Column("days_since_last_inspection", sa.Integer(), nullable=True),
        sa.Column("building_type", sa.Text(), nullable=True),
        sa.UniqueConstraint("building_id", "feature_date", name="uq_building_features_building_date"),
    )

    op.create_index(
        "idx_features_city_date",
        "building_features",
        ["city_id", sa.text("feature_date DESC")],
    )
    op.create_index(
        "idx_features_building",
        "building_features",
        ["building_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_features_building", table_name="building_features")
    op.drop_index("idx_features_city_date", table_name="building_features")
    op.drop_table("building_features")
