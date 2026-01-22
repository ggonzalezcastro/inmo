"""Add appointments tables

Revision ID: b2c4d5e6f7a8
Revises: a6f3f625b64a
Create Date: 2025-11-26 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b2c4d5e6f7a8'
down_revision: Union[str, None] = 'a6f3f625b64a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enums if they don't exist using raw SQL
    conn = op.get_bind()
    
    # Check and create appointmenttype enum
    result = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM pg_type WHERE typname = 'appointmenttype'
        )
    """))
    if not result.scalar():
        conn.execute(sa.text("""
            CREATE TYPE appointmenttype AS ENUM 
            ('property_visit', 'virtual_meeting', 'phone_call', 'office_meeting', 'other')
        """))
        conn.commit()
    
    # Check and create appointmentstatus enum
    result = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM pg_type WHERE typname = 'appointmentstatus'
        )
    """))
    if not result.scalar():
        conn.execute(sa.text("""
            CREATE TYPE appointmentstatus AS ENUM 
            ('scheduled', 'confirmed', 'cancelled', 'completed', 'no_show')
        """))
        conn.commit()
    
    # Create appointments table
    op.create_table('appointments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=True),
        sa.Column('appointment_type', sa.Enum('property_visit', 'virtual_meeting', 'phone_call', 'office_meeting', 'other', name='appointmenttype', create_type=False), nullable=False),
        sa.Column('status', sa.Enum('scheduled', 'confirmed', 'cancelled', 'completed', 'no_show', name='appointmentstatus', create_type=False), nullable=False),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=False),
        sa.Column('location', sa.String(length=500), nullable=True),
        sa.Column('property_address', sa.String(length=500), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('lead_notes', sa.Text(), nullable=True),
        sa.Column('reminder_sent_24h', sa.Boolean(), nullable=False),
        sa.Column('reminder_sent_1h', sa.Boolean(), nullable=False),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancellation_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_appointment_datetime', 'appointments', ['start_time', 'end_time'], unique=False)
    op.create_index('idx_appointment_lead_status', 'appointments', ['lead_id', 'status'], unique=False)
    op.create_index('idx_appointment_agent_status', 'appointments', ['agent_id', 'status'], unique=False)
    op.create_index(op.f('ix_appointments_id'), 'appointments', ['id'], unique=False)
    op.create_index(op.f('ix_appointments_lead_id'), 'appointments', ['lead_id'], unique=False)
    op.create_index(op.f('ix_appointments_agent_id'), 'appointments', ['agent_id'], unique=False)
    op.create_index(op.f('ix_appointments_status'), 'appointments', ['status'], unique=False)
    op.create_index(op.f('ix_appointments_start_time'), 'appointments', ['start_time'], unique=False)

    # Create availability_slots table
    op.create_table('availability_slots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=True),
        sa.Column('day_of_week', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('valid_from', sa.Date(), nullable=False),
        sa.Column('valid_until', sa.Date(), nullable=True),
        sa.Column('appointment_type', sa.Enum('property_visit', 'virtual_meeting', 'phone_call', 'office_meeting', 'other', name='appointmenttype', create_type=False), nullable=True),
        sa.Column('slot_duration_minutes', sa.Integer(), nullable=False),
        sa.Column('max_appointments_per_slot', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_availability_slots_id'), 'availability_slots', ['id'], unique=False)
    op.create_index(op.f('ix_availability_slots_agent_id'), 'availability_slots', ['agent_id'], unique=False)

    # Create appointment_blocks table
    op.create_table('appointment_blocks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=True),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_recurring', sa.Boolean(), nullable=False),
        sa.Column('recurrence_pattern', sa.String(length=100), nullable=True),
        sa.Column('recurrence_end_date', sa.Date(), nullable=True),
        sa.Column('reason', sa.String(length=200), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_block_datetime', 'appointment_blocks', ['start_time', 'end_time'], unique=False)
    op.create_index(op.f('ix_appointment_blocks_id'), 'appointment_blocks', ['id'], unique=False)
    op.create_index(op.f('ix_appointment_blocks_agent_id'), 'appointment_blocks', ['agent_id'], unique=False)
    op.create_index(op.f('ix_appointment_blocks_start_time'), 'appointment_blocks', ['start_time'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_appointment_blocks_start_time'), table_name='appointment_blocks')
    op.drop_index(op.f('ix_appointment_blocks_agent_id'), table_name='appointment_blocks')
    op.drop_index(op.f('ix_appointment_blocks_id'), table_name='appointment_blocks')
    op.drop_index('idx_block_datetime', table_name='appointment_blocks')
    op.drop_table('appointment_blocks')
    op.drop_index(op.f('ix_availability_slots_agent_id'), table_name='availability_slots')
    op.drop_index(op.f('ix_availability_slots_id'), table_name='availability_slots')
    op.drop_table('availability_slots')
    op.drop_index(op.f('ix_appointments_start_time'), table_name='appointments')
    op.drop_index(op.f('ix_appointments_status'), table_name='appointments')
    op.drop_index(op.f('ix_appointments_agent_id'), table_name='appointments')
    op.drop_index(op.f('ix_appointments_lead_id'), table_name='appointments')
    op.drop_index(op.f('ix_appointments_id'), table_name='appointments')
    op.drop_index('idx_appointment_agent_status', table_name='appointments')
    op.drop_index('idx_appointment_lead_status', table_name='appointments')
    op.drop_index('idx_appointment_datetime', table_name='appointments')
    op.drop_table('appointments')
    # Drop enums
    sa.Enum(name='appointmentstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='appointmenttype').drop(op.get_bind(), checkfirst=True)

