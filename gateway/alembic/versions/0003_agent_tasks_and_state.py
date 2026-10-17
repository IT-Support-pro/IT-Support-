"""agent tasks and agent state

Revision ID: 0003_agent_tasks_and_state
Revises: 0002_network_datetime_fbr
Create Date: 2026-10-14 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0003_agent_tasks_and_state'
down_revision: Union[str, None] = '0002_network_datetime_fbr'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Add agent_state column to devices
    op.add_column(
        'devices',
        sa.Column('agent_state', sa.String(length=20), server_default='RUNNING', nullable=False)
    )

    # 2. Create agent_tasks table
    op.create_table(
        'agent_tasks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('device_pk', sa.String(length=36), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='PENDING', nullable=False),
        sa.Column('requested_by', sa.String(length=100), nullable=False),
        sa.Column('requested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('result_text', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['device_pk'], ['devices.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_agent_tasks_id', 'agent_tasks', ['id'], unique=False)
    op.create_index('ix_agent_tasks_device_pk', 'agent_tasks', ['device_pk'], unique=False)
    op.create_index('ix_agent_tasks_status', 'agent_tasks', ['status'], unique=False)
    op.create_index('ix_agent_tasks_requested_at', 'agent_tasks', ['requested_at'], unique=False)

def downgrade() -> None:
    op.drop_index('ix_agent_tasks_requested_at', table_name='agent_tasks')
    op.drop_index('ix_agent_tasks_status', table_name='agent_tasks')
    op.drop_index('ix_agent_tasks_device_pk', table_name='agent_tasks')
    op.drop_index('ix_agent_tasks_id', table_name='agent_tasks')
    op.drop_table('agent_tasks')
    op.drop_column('devices', 'agent_state')
