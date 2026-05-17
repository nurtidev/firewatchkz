"""Create weather_history table

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-13
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0006'
down_revision: Union[str, None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'weather_history',
        sa.Column('ts', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('h3_cell', sa.Text(), nullable=False),
        sa.Column('temp_c', sa.Numeric(), nullable=True),
        sa.Column('wind_ms', sa.Numeric(), nullable=True),
        sa.Column('humidity_pct', sa.Numeric(), nullable=True),
        sa.Column('precipitation_mm', sa.Numeric(), nullable=True),
        sa.PrimaryKeyConstraint('ts', 'h3_cell'),
    )
    op.create_index('idx_weather_ts', 'weather_history', ['ts'], postgresql_using='btree')


def downgrade() -> None:
    op.drop_index('idx_weather_ts', table_name='weather_history')
    op.drop_table('weather_history')
