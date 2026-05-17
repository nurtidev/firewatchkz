"""Create risk_scores table

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "risk_scores",
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
        sa.Column("city_id", sa.Text(), nullable=False),
        sa.Column(
            "computed_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
        ),
        sa.Column("baseline_score", sa.Numeric(), nullable=False),
        sa.Column("dynamic_modifier", sa.Numeric(), server_default="1.0"),
        sa.Column("final_score", sa.Numeric(), nullable=False),
        sa.Column("shap_values", sa.JSON(), nullable=True),
        sa.Column(
            "score_date",
            sa.Date(),
            nullable=False,
            server_default=sa.text("CURRENT_DATE"),
        ),
        sa.UniqueConstraint("building_id", "score_date", name="uq_risk_scores_building_date"),
    )

    op.create_index(
        "idx_risk_city_score",
        "risk_scores",
        ["city_id", sa.text("final_score DESC")],
    )
    op.create_index(
        "idx_risk_building",
        "risk_scores",
        ["building_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_risk_building", table_name="risk_scores")
    op.drop_index("idx_risk_city_score", table_name="risk_scores")
    op.drop_table("risk_scores")
