"""create broker_plans and add plan_id to brokers

Revision ID: w4r5s6t7u8v9
Revises: v3q4r5s6t7u8
Create Date: 2026-04-02 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'w4r5s6t7u8v9'
down_revision = 'v3q4r5s6t7u8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create broker_plans table
    op.create_table(
        'broker_plans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.String(255), nullable=True),
        sa.Column('max_leads', sa.Integer(), nullable=True),
        sa.Column('max_users', sa.Integer(), nullable=True),
        sa.Column('max_messages_per_month', sa.Integer(), nullable=True),
        sa.Column('max_llm_cost_per_month', sa.Float(), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_index(op.f('ix_broker_plans_id'), 'broker_plans', ['id'])

    # 2. Seed default plans
    op.execute("""
        INSERT INTO broker_plans (name, description, max_leads, max_users, max_messages_per_month, max_llm_cost_per_month, is_default, is_active)
        VALUES
            ('Free',  'Plan gratuito con límites básicos',    500,  3,  1000, 10.0,  true,  true),
            ('Pro',   'Plan profesional sin límites estrictos', 5000, 10, 20000, 200.0, false, true),
            ('Enterprise', 'Plan empresarial ilimitado',        NULL, NULL, NULL, NULL, false, true)
    """)

    # 3. Add plan_id to brokers
    op.add_column(
        'brokers',
        sa.Column('plan_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_brokers_plan_id',
        'brokers', 'broker_plans',
        ['plan_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_index('idx_brokers_plan_id', 'brokers', ['plan_id'])


def downgrade() -> None:
    op.drop_index('idx_brokers_plan_id', table_name='brokers')
    op.drop_constraint('fk_brokers_plan_id', 'brokers', type_='foreignkey')
    op.drop_column('brokers', 'plan_id')
    op.drop_index(op.f('ix_broker_plans_id'), table_name='broker_plans')
    op.drop_table('broker_plans')
