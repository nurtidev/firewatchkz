"""core entities: buildings, users, audit_log

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-13
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import geoalchemy2

revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # users table (create before buildings — buildings.approved_by refs users)
    op.create_table(
        'users',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('full_name', sa.String(), nullable=True),
        sa.Column('role', sa.String(), nullable=False),  # admin/analyst/inspector/viewer
        sa.Column('password_hash', sa.String(), nullable=True),
        sa.Column('organization_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('last_login_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint('email'),
    )

    # Seed 4 test users (password hashes are bcrypt of obvious passwords for dev only)
    op.execute("""
        INSERT INTO users (id, email, full_name, role, password_hash) VALUES
        ('user-admin-1',    'admin@firewatch.kz',    'Admin User',    'admin',    '$2b$12$placeholder_admin'),
        ('user-analyst-1',  'analyst@firewatch.kz',  'Analyst User',  'analyst',  '$2b$12$placeholder_analyst'),
        ('user-inspector-1','inspector@firewatch.kz', 'Inspector User','inspector','$2b$12$placeholder_inspector'),
        ('user-viewer-1',   'viewer@firewatch.kz',   'Viewer User',   'viewer',   '$2b$12$placeholder_viewer')
    """)

    # buildings table
    op.create_table(
        'buildings',
        sa.Column('id', sa.String(), primary_key=True, server_default=sa.text("gen_random_uuid()::text")),
        sa.Column('city_id', sa.String(), sa.ForeignKey('cities.id'), nullable=False),
        sa.Column('address', sa.Text(), nullable=False),
        sa.Column('address_norm', sa.Text(), nullable=False),
        sa.Column('geom', geoalchemy2.types.Geometry('POLYGON', srid=4326, spatial_index=False), nullable=True),
        sa.Column('centroid', geoalchemy2.types.Geometry('POINT', srid=4326, spatial_index=False), nullable=True),
        sa.Column('building_type', sa.String(), nullable=True),  # residential/commercial/industrial/social/educational/medical
        sa.Column('floors_above', sa.Integer(), nullable=True),
        sa.Column('floors_below', sa.Integer(), nullable=True),
        sa.Column('height_m', sa.Numeric(), nullable=True),
        sa.Column('total_area_sqm', sa.Numeric(), nullable=True),
        sa.Column('year_built', sa.Integer(), nullable=True),
        sa.Column('wall_material', sa.String(), nullable=True),
        sa.Column('fire_resistance', sa.Integer(), nullable=True),   # I-V степень (1-5)
        sa.Column('fire_hazard_class', sa.String(), nullable=True),  # Ф1-Ф5
        sa.Column('source', sa.String(), nullable=False),            # osm/2gis/manual/document_extract
        sa.Column('external_id', sa.String(), nullable=True),        # ID в источнике
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.UniqueConstraint('source', 'external_id', name='uq_buildings_source_external_id'),
    )
    op.create_index('idx_buildings_city', 'buildings', ['city_id'])
    op.create_index('idx_buildings_geom', 'buildings', ['geom'], postgresql_using='gist')
    op.create_index('idx_buildings_centroid', 'buildings', ['centroid'], postgresql_using='gist')

    # audit_log table
    op.create_table(
        'audit_log',
        sa.Column('id', sa.String(), primary_key=True, server_default=sa.text("gen_random_uuid()::text")),
        sa.Column('user_id', sa.String(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('entity_type', sa.String(), nullable=False),
        sa.Column('entity_id', sa.String(), nullable=True),
        sa.Column('changes', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('occurred_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_audit_entity', 'audit_log', ['entity_type', 'entity_id'])
    op.create_index('idx_audit_time', 'audit_log', ['occurred_at'])

def downgrade() -> None:
    op.drop_table('audit_log')
    op.drop_table('buildings')
    op.drop_table('users')
