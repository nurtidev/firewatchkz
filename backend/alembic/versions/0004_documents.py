"""operational_cards and card_extractions

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-13
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # card_extractions must exist before operational_cards references it
    op.create_table(
        'card_extractions',
        sa.Column('id', sa.String(), primary_key=True, server_default=sa.text("gen_random_uuid()::text")),
        sa.Column('card_id', sa.String(), nullable=False),   # FK added after operational_cards created
        sa.Column('model_version', sa.String(), nullable=False),
        sa.Column('extracted_data', sa.JSON(), nullable=False),
        sa.Column('field_confidences', sa.JSON(), nullable=False),
        sa.Column('vulnerabilities', sa.JSON(), nullable=True),
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('extraction_cost_usd', sa.Numeric(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_extractions_card', 'card_extractions', ['card_id'])

    # operational_cards
    op.create_table(
        'operational_cards',
        sa.Column('id', sa.String(), primary_key=True, server_default=sa.text("gen_random_uuid()::text")),
        sa.Column('building_id', sa.String(), sa.ForeignKey('buildings.id', ondelete='SET NULL'), nullable=True),
        sa.Column('uploaded_by', sa.String(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('uploaded_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('file_url', sa.Text(), nullable=False),
        sa.Column('file_name', sa.Text(), nullable=False),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('file_mime', sa.String(), nullable=True),
        # status flow: uploaded → converting → ready_for_extraction → extracting → extracted → review → approved / rejected
        sa.Column('status', sa.String(), nullable=False, server_default='uploaded'),
        sa.Column('extraction_id', sa.String(), sa.ForeignKey('card_extractions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('approved_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('approved_by', sa.String(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        # storage keys for converted PDF and thumbnail
        sa.Column('converted_key', sa.Text(), nullable=True),
        sa.Column('thumbnail_key', sa.Text(), nullable=True),
    )
    op.create_index('idx_cards_building', 'operational_cards', ['building_id'])
    op.create_index('idx_cards_status', 'operational_cards', ['status'])
    op.create_index('idx_cards_uploaded_by', 'operational_cards', ['uploaded_by'])

    # Now add FK from card_extractions.card_id → operational_cards.id
    op.create_foreign_key(
        'fk_extractions_card_id',
        'card_extractions', 'operational_cards',
        ['card_id'], ['id'],
        ondelete='CASCADE',
    )

def downgrade() -> None:
    op.drop_constraint('fk_extractions_card_id', 'card_extractions', type_='foreignkey')
    op.drop_table('operational_cards')
    op.drop_table('card_extractions')
