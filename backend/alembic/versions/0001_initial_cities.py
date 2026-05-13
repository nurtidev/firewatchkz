"""initial cities table

Revision ID: 0001
Revises:
Create Date: 2026-05-13

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import geoalchemy2

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        'cities',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('center', geoalchemy2.types.Geometry('POINT', srid=4326), nullable=True),
        sa.Column('zoom', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )

    op.execute("""
        INSERT INTO cities (id, code, name, center, zoom)
        VALUES (
            'astana',
            'astana',
            'Астана',
            ST_SetSRID(ST_MakePoint(71.4460, 51.1801), 4326),
            12
        )
    """)


def downgrade() -> None:
    op.drop_table('cities')
