"""incidents, hydrants, fire_stations, operations, inspections

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-13
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import geoalchemy2

revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # incidents
    op.create_table(
        'incidents',
        sa.Column('id', sa.String(), primary_key=True, server_default=sa.text("gen_random_uuid()::text")),
        sa.Column('occurred_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('geom', geoalchemy2.types.Geometry('POINT', srid=4326, spatial_index=False), nullable=True),
        sa.Column('address_text', sa.Text(), nullable=True),
        sa.Column('district', sa.String(), nullable=True),          # kept for v1 compat
        sa.Column('building_id', sa.String(), sa.ForeignKey('buildings.id', ondelete='SET NULL'), nullable=True),
        sa.Column('incident_type', sa.String(), nullable=True),     # fire/smoke/false_alarm/other
        sa.Column('building_type', sa.String(), nullable=True),     # residential/commercial/...
        sa.Column('cause', sa.String(), nullable=True),             # electrical/open_flame/arson/children/other
        sa.Column('severity', sa.String(), nullable=True),          # low/medium/high/critical
        sa.Column('damage_tenge', sa.Numeric(), nullable=True),
        sa.Column('casualties', sa.Integer(), server_default='0', nullable=False),
        sa.Column('source', sa.String(), nullable=False, server_default='csv'),
        sa.Column('external_id', sa.String(), nullable=True),
        sa.Column('lat', sa.Numeric(), nullable=True),
        sa.Column('lon', sa.Numeric(), nullable=True),
    )
    op.create_index('idx_incidents_geom', 'incidents', ['geom'], postgresql_using='gist')
    op.create_index('idx_incidents_time', 'incidents', ['occurred_at'])
    op.create_index('idx_incidents_building', 'incidents', ['building_id'])
    op.create_index('idx_incidents_district', 'incidents', ['district'])

    # hydrants
    op.create_table(
        'hydrants',
        sa.Column('id', sa.String(), primary_key=True, server_default=sa.text("gen_random_uuid()::text")),
        sa.Column('city', sa.String(), nullable=True),
        sa.Column('district', sa.String(), nullable=True),
        sa.Column('geom', geoalchemy2.types.Geometry('POINT', srid=4326, spatial_index=False), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='working'),  # working/maintenance/out_of_service
        sa.Column('capacity_l_s', sa.Numeric(), nullable=True),
        sa.Column('last_check_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('winter_access', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('lat', sa.Numeric(), nullable=True),
        sa.Column('lon', sa.Numeric(), nullable=True),
        sa.Column('external_id', sa.String(), nullable=True),
    )
    op.create_index('idx_hydrants_geom', 'hydrants', ['geom'], postgresql_using='gist')
    op.create_index('idx_hydrants_city', 'hydrants', ['city'])

    # fire_stations
    op.create_table(
        'fire_stations',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('city', sa.String(), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('district', sa.String(), nullable=True),
        sa.Column('geom', geoalchemy2.types.Geometry('POINT', srid=4326, spatial_index=False), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('units', sa.Integer(), nullable=True),
        sa.Column('staff_count', sa.Integer(), nullable=True),
        sa.Column('lat', sa.Numeric(), nullable=True),
        sa.Column('lon', sa.Numeric(), nullable=True),
    )
    op.create_index('idx_stations_geom', 'fire_stations', ['geom'], postgresql_using='gist')
    op.create_index('idx_stations_city', 'fire_stations', ['city'])

    # operations (response logs)
    op.create_table(
        'operations',
        sa.Column('id', sa.String(), primary_key=True, server_default=sa.text("gen_random_uuid()::text")),
        sa.Column('date', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('city', sa.String(), nullable=True),
        sa.Column('district', sa.String(), nullable=True),
        sa.Column('station_id', sa.String(), sa.ForeignKey('fire_stations.id', ondelete='SET NULL'), nullable=True),
        sa.Column('incident_id', sa.String(), sa.ForeignKey('incidents.id', ondelete='SET NULL'), nullable=True),
        sa.Column('response_time_min', sa.Numeric(), nullable=True),
        sa.Column('outcome', sa.String(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
    )
    op.create_index('idx_operations_city', 'operations', ['city'])

    # inspections
    op.create_table(
        'inspections',
        sa.Column('id', sa.String(), primary_key=True, server_default=sa.text("gen_random_uuid()::text")),
        sa.Column('building_id', sa.String(), sa.ForeignKey('buildings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('inspector_id', sa.String(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('inspected_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('violations_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('outcome', sa.String(), nullable=True),   # passed/failed/requires_revisit
        sa.Column('notes', sa.Text(), nullable=True),
    )
    op.create_index('idx_inspections_building', 'inspections', ['building_id'])
    op.create_index('idx_inspections_time', 'inspections', ['inspected_at'])

def downgrade() -> None:
    op.drop_table('inspections')
    op.drop_table('operations')
    op.drop_table('fire_stations')
    op.drop_table('hydrants')
    op.drop_table('incidents')
