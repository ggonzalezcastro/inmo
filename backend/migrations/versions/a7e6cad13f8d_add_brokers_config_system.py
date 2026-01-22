"""add_brokers_config_system

Revision ID: a7e6cad13f8d
Revises: 9a1d5be06801
Create Date: 2025-12-01 18:44:53.666058

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a7e6cad13f8d'
down_revision: Union[str, None] = '9a1d5be06801'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create UserRole enum if it doesn't exist
    conn = op.get_bind()
    result = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM pg_type WHERE typname = 'userrole'
        )
    """))
    if not result.scalar():
        conn.execute(sa.text("""
            CREATE TYPE userrole AS ENUM 
            ('superadmin', 'admin', 'agent')
        """))
        conn.commit()
    
    # Check if brokers table exists
    conn = op.get_bind()
    result = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = 'brokers'
        )
    """))
    brokers_exists = result.scalar()
    
    # Create brokers table if it doesn't exist
    if not brokers_exists:
        op.create_table('brokers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=True),
        sa.Column('contact_phone', sa.String(length=50), nullable=True),
        sa.Column('contact_email', sa.String(length=200), nullable=True),
        sa.Column('business_hours', sa.String(length=100), nullable=True),
        sa.Column('service_zones', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
        op.create_index(op.f('ix_brokers_id'), 'brokers', ['id'], unique=False)
        op.create_index('ix_brokers_slug', 'brokers', ['slug'], unique=True)
    
    # Check if broker_prompt_configs table exists
    result = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = 'broker_prompt_configs'
        )
    """))
    prompt_configs_exists = result.scalar()
    
    # Create broker_prompt_configs table if it doesn't exist
    if not prompt_configs_exists:
        op.create_table('broker_prompt_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('broker_id', sa.Integer(), nullable=False),
        sa.Column('agent_name', sa.String(length=100), nullable=True),
        sa.Column('agent_role', sa.String(length=200), nullable=True),
        sa.Column('identity_prompt', sa.Text(), nullable=True),
        sa.Column('business_context', sa.Text(), nullable=True),
        sa.Column('agent_objective', sa.Text(), nullable=True),
        sa.Column('data_collection_prompt', sa.Text(), nullable=True),
        sa.Column('behavior_rules', sa.Text(), nullable=True),
        sa.Column('restrictions', sa.Text(), nullable=True),
        sa.Column('situation_handlers', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('output_format', sa.Text(), nullable=True),
        sa.Column('full_custom_prompt', sa.Text(), nullable=True),
        sa.Column('enable_appointment_booking', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('tools_instructions', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['broker_id'], ['brokers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('broker_id')
    )
        op.create_index(op.f('ix_broker_prompt_configs_id'), 'broker_prompt_configs', ['id'], unique=False)
        op.create_index('ix_broker_prompt_configs_broker_id', 'broker_prompt_configs', ['broker_id'], unique=True)
    
    # Check if broker_lead_configs table exists
    result = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = 'broker_lead_configs'
        )
    """))
    lead_configs_exists = result.scalar()
    
    # Create broker_lead_configs table if it doesn't exist
    if not lead_configs_exists:
        op.create_table('broker_lead_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('broker_id', sa.Integer(), nullable=False),
        sa.Column('field_weights', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('cold_max_score', sa.Integer(), nullable=False, server_default='20'),
        sa.Column('warm_max_score', sa.Integer(), nullable=False, server_default='50'),
        sa.Column('hot_min_score', sa.Integer(), nullable=False, server_default='50'),
        sa.Column('qualified_min_score', sa.Integer(), nullable=False, server_default='75'),
        sa.Column('field_priority', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('alert_on_hot_lead', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('alert_score_threshold', sa.Integer(), nullable=False, server_default='70'),
        sa.Column('alert_email', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['broker_id'], ['brokers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('broker_id')
    )
        op.create_index(op.f('ix_broker_lead_configs_id'), 'broker_lead_configs', ['id'], unique=False)
        op.create_index('ix_broker_lead_configs_broker_id', 'broker_lead_configs', ['broker_id'], unique=True)
    
    # Check if broker_id column exists
    check_broker_id = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'broker_id'
        )
    """))
    has_broker_id = check_broker_id.scalar()
    
    # Add broker_id to users table if it doesn't exist
    if not has_broker_id:
        op.add_column('users', sa.Column('broker_id', sa.Integer(), nullable=True))
        op.create_foreign_key(
            'users_broker_id_fkey',
            'users', 'brokers',
            ['broker_id'], ['id'],
            ondelete='CASCADE'
        )
        op.create_index('ix_users_broker_id', 'users', ['broker_id'], unique=False)
    
    # Migrate broker_name to name (if broker_name exists)
    # Check if name column already exists
    conn = op.get_bind()
    check_name = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'name'
        )
    """))
    has_name = check_name.scalar()
    
    check_broker_name = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'broker_name'
        )
    """))
    has_broker_name = check_broker_name.scalar()
    
    if has_broker_name and not has_name:
        # Rename broker_name to name
        op.execute("ALTER TABLE users RENAME COLUMN broker_name TO name;")
    elif not has_name:
        # Create name column from broker_name if it exists, or add new column
        if has_broker_name:
            op.execute("ALTER TABLE users ADD COLUMN name VARCHAR(100);")
            op.execute("UPDATE users SET name = broker_name WHERE name IS NULL;")
            op.execute("ALTER TABLE users ALTER COLUMN name SET NOT NULL;")
            op.execute("ALTER TABLE users DROP COLUMN broker_name;")
        else:
            op.execute("ALTER TABLE users ADD COLUMN name VARCHAR(100) NOT NULL DEFAULT 'User';")
    
    # Update role column to use UserRole enum
    # The enum has values in UPPERCASE: SUPERADMIN, ADMIN, AGENT
    # First, update existing values to match enum values (UPPERCASE)
    op.execute("""
        UPDATE users 
        SET role = CASE 
            WHEN LOWER(role) = 'broker' THEN 'ADMIN'
            WHEN UPPER(role) = 'SUPERADMIN' THEN 'SUPERADMIN'
            WHEN UPPER(role) = 'ADMIN' THEN 'ADMIN'
            WHEN UPPER(role) = 'AGENT' THEN 'AGENT'
            ELSE 'AGENT'  -- Default fallback
        END;
    """)
    
    # Change role column type to use enum
    # Check if column is already enum type
    check_role_type = conn.execute(sa.text("""
        SELECT data_type FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'role'
    """))
    role_type_result = check_role_type.fetchone()
    role_type = role_type_result[0] if role_type_result else None
    
    if role_type and role_type != 'USER-DEFINED':
        # Only convert if not already an enum
        op.execute("ALTER TABLE users ALTER COLUMN role TYPE userrole USING role::userrole;")


def downgrade() -> None:
    # Revert role column
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(20) USING role::text;")
    
    # Restore broker_name column
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS broker_name VARCHAR(100);")
    op.execute("UPDATE users SET broker_name = name WHERE broker_name IS NULL;")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS name CASCADE;")
    op.execute("ALTER TABLE users RENAME COLUMN broker_name TO broker_name;")
    
    # Drop broker_id from users
    op.drop_constraint('users_broker_id_fkey', 'users', type_='foreignkey')
    op.drop_index('ix_users_broker_id', table_name='users')
    op.drop_column('users', 'broker_id')
    
    # Drop broker tables
    op.drop_index('ix_broker_lead_configs_broker_id', table_name='broker_lead_configs')
    op.drop_index(op.f('ix_broker_lead_configs_id'), table_name='broker_lead_configs')
    op.drop_table('broker_lead_configs')
    
    op.drop_index('ix_broker_prompt_configs_broker_id', table_name='broker_prompt_configs')
    op.drop_index(op.f('ix_broker_prompt_configs_id'), table_name='broker_prompt_configs')
    op.drop_table('broker_prompt_configs')
    
    op.drop_index('ix_brokers_slug', table_name='brokers')
    op.drop_index(op.f('ix_brokers_id'), table_name='brokers')
    op.drop_table('brokers')
    
    # Note: We don't drop the userrole enum as it might be used elsewhere
