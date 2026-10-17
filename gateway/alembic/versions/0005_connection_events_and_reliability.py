"""connection events and reliability

Revision ID: 0005_connection_events_and_reliability
Revises: 0004_fbr_registrations_and_invoices
Create Date: 2026-10-16 11:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0005_connection_events_and_reliability'
down_revision: Union[str, None] = '0004_fbr_registrations_and_invoices'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Add reliability columns to devices
    with op.batch_alter_table('devices') as batch_op:
        batch_op.add_column(sa.Column('connection_status', sa.String(length=20), server_default='ONLINE', nullable=False))
        batch_op.add_column(sa.Column('offline_reason_code', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('offline_reason_text', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('offline_since', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('expected_timezone', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('muted_rules_json', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('clock_raw_json', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('reading_stale', sa.Boolean(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('consecutive_heartbeats_ok', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('capabilities_json', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('last_error_text', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('w32time_running', sa.Boolean(), nullable=True))

    # 2. Add expected_timezone to stores
    with op.batch_alter_table('stores') as batch_op:
        batch_op.add_column(sa.Column('expected_timezone', sa.String(length=100), server_default='Pakistan Standard Time', nullable=True))

    # 3. Add resolution and resolved_by to alerts
    with op.batch_alter_table('alerts') as batch_op:
        batch_op.add_column(sa.Column('resolution', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('resolved_by', sa.String(length=100), nullable=True))

    # 4. Create connection_events table
    op.create_table(
        'connection_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('device_pk', sa.String(length=36), nullable=False),
        sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('type', sa.String(length=30), nullable=False),
        sa.Column('reason_code', sa.String(length=50), nullable=True),
        sa.Column('reason_text', sa.Text(), nullable=True),
        sa.Column('duration_sec', sa.Float(), nullable=True),
        sa.Column('details_json', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['device_pk'], ['devices.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_connection_events_id', 'connection_events', ['id'], unique=False)
    op.create_index('ix_connection_events_device_pk', 'connection_events', ['device_pk'], unique=False)
    op.create_index('ix_connection_events_ts', 'connection_events', ['ts'], unique=False)
    op.create_index('ix_connection_events_type', 'connection_events', ['type'], unique=False)
    op.create_index('ix_connection_events_device_ts', 'connection_events', ['device_pk', 'ts'], unique=False)

    # 5. Create gateway_state table
    op.create_table(
        'gateway_state',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('last_alive', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at_utc', sa.DateTime(timezone=True), nullable=False),
        sa.Column('version', sa.String(length=50), server_default='1.1.0', nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_gateway_state_id', 'gateway_state', ['id'], unique=False)

    # 6. Create alert_checks table
    op.create_table(
        'alert_checks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('alert_id', sa.Integer(), nullable=False),
        sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('by', sa.String(length=100), nullable=False),
        sa.Column('result', sa.String(length=30), nullable=False),
        sa.Column('observed_value', sa.String(length=100), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['alert_id'], ['alerts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_alert_checks_id', 'alert_checks', ['id'], unique=False)
    op.create_index('ix_alert_checks_alert_id', 'alert_checks', ['alert_id'], unique=False)

    # 7. Create light_metrics table
    op.create_table(
        'light_metrics',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('device_pk', sa.String(length=36), nullable=False),
        sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('cpu_pct', sa.Float(), nullable=False),
        sa.Column('ram_pct', sa.Float(), nullable=False),
        sa.Column('system_disk_pct', sa.Float(), nullable=True),
        sa.Column('internet_ok', sa.Boolean(), server_default='1', nullable=False),
        sa.ForeignKeyConstraint(['device_pk'], ['devices.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_light_metrics_id', 'light_metrics', ['id'], unique=False)
    op.create_index('ix_light_metrics_device_pk', 'light_metrics', ['device_pk'], unique=False)
    op.create_index('ix_light_metrics_ts', 'light_metrics', ['ts'], unique=False)
    op.create_index('ix_light_metrics_device_ts', 'light_metrics', ['device_pk', 'ts'], unique=False)

def downgrade() -> None:
    op.drop_table('light_metrics')
    op.drop_table('alert_checks')
    op.drop_table('gateway_state')
    op.drop_table('connection_events')
    with op.batch_alter_table('alerts') as batch_op:
        batch_op.drop_column('resolved_by')
        batch_op.drop_column('resolution')
    with op.batch_alter_table('stores') as batch_op:
        batch_op.drop_column('expected_timezone')
    with op.batch_alter_table('devices') as batch_op:
        batch_op.drop_column('w32time_running')
        batch_op.drop_column('last_error_text')
        batch_op.drop_column('capabilities_json')
        batch_op.drop_column('consecutive_heartbeats_ok')
        batch_op.drop_column('reading_stale')
        batch_op.drop_column('clock_raw_json')
        batch_op.drop_column('muted_rules_json')
        batch_op.drop_column('expected_timezone')
        batch_op.drop_column('offline_since')
        batch_op.drop_column('offline_reason_text')
        batch_op.drop_column('offline_reason_code')
        batch_op.drop_column('connection_status')
