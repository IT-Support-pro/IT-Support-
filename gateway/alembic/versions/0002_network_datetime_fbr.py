"""network, datetime, fbr and alert rules

Revision ID: 0002_network_datetime_fbr
Revises: 0001_initial_schema
Create Date: 2026-10-14 08:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0002_network_datetime_fbr'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Add datetime, FBR, and network columns to devices table
    op.add_column('devices', sa.Column('local_time', sa.String(length=50), nullable=True))
    op.add_column('devices', sa.Column('utc_time', sa.DateTime(timezone=True), nullable=True))
    op.add_column('devices', sa.Column('timezone_name', sa.String(length=100), nullable=True))
    op.add_column('devices', sa.Column('utc_offset_minutes', sa.Integer(), nullable=True))
    op.add_column('devices', sa.Column('uptime_sec', sa.Float(), nullable=True))
    op.add_column('devices', sa.Column('clock_offset_sec', sa.Float(), nullable=True))

    op.add_column('devices', sa.Column('fbr_status', sa.String(length=50), server_default='NOT_CONFIGURED', nullable=True))
    op.add_column('devices', sa.Column('fbr_ok', sa.Boolean(), nullable=True))
    op.add_column('devices', sa.Column('fbr_latency_ms', sa.Float(), nullable=True))
    op.add_column('devices', sa.Column('fbr_http_status', sa.Integer(), nullable=True))
    op.add_column('devices', sa.Column('fbr_last_check', sa.DateTime(timezone=True), nullable=True))
    op.add_column('devices', sa.Column('fbr_last_ok_time', sa.DateTime(timezone=True), nullable=True))
    op.add_column('devices', sa.Column('fbr_consecutive_failures', sa.Integer(), server_default='0', nullable=False))
    op.add_column('devices', sa.Column('fbr_error', sa.String(length=255), nullable=True))
    op.add_column('devices', sa.Column('network_details_json', sa.JSON(), nullable=True))

    # 2. Create fbr_checks history table
    op.create_table(
        'fbr_checks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('device_pk', sa.String(length=36), nullable=False),
        sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ok', sa.Boolean(), nullable=False),
        sa.Column('latency_ms', sa.Float(), nullable=True),
        sa.Column('http_status', sa.Integer(), nullable=True),
        sa.Column('error', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['device_pk'], ['devices.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_fbr_checks_id', 'fbr_checks', ['id'], unique=False)
    op.create_index('ix_fbr_checks_device_pk', 'fbr_checks', ['device_pk'], unique=False)
    op.create_index('ix_fbr_checks_ts', 'fbr_checks', ['ts'], unique=False)

    # 3. Seed new default Alert Rules (clock_drift, timezone_mismatch, fbr_down)
    alert_rules_table = sa.table(
        'alert_rules',
        sa.column('rule_key', sa.String),
        sa.column('name', sa.String),
        sa.column('severity', sa.String),
        sa.column('threshold_value', sa.Float),
        sa.column('duration_seconds', sa.Integer),
        sa.column('enabled', sa.Boolean),
        sa.column('description', sa.String)
    )

    op.bulk_insert(
        alert_rules_table,
        [
            {
                "rule_key": "clock_drift",
                "name": "POS Clock Drift",
                "severity": "warning",
                "threshold_value": 120.0,
                "duration_seconds": 0,
                "enabled": True,
                "description": "POS system clock drifts > 120s (warning) or > 600s (critical) from gateway UTC time"
            },
            {
                "rule_key": "timezone_mismatch",
                "name": "Timezone Configuration Mismatch",
                "severity": "warning",
                "threshold_value": 0.0,
                "duration_seconds": 0,
                "enabled": True,
                "description": "POS timezone differs from EXPECTED_TIMEZONE setting"
            },
            {
                "rule_key": "fbr_down",
                "name": "FBR Fiscal Portal Unreachable",
                "severity": "critical",
                "threshold_value": 2.0,
                "duration_seconds": 0,
                "enabled": True,
                "description": "FBR fiscal invoice portal unreachable for 2 consecutive checks"
            }
        ]
    )

def downgrade() -> None:
    op.drop_index('ix_fbr_checks_ts', table_name='fbr_checks')
    op.drop_index('ix_fbr_checks_device_pk', table_name='fbr_checks')
    op.drop_index('ix_fbr_checks_id', table_name='fbr_checks')
    op.drop_table('fbr_checks')

    op.drop_column('devices', 'network_details_json')
    op.drop_column('devices', 'fbr_error')
    op.drop_column('devices', 'fbr_consecutive_failures')
    op.drop_column('devices', 'fbr_last_ok_time')
    op.drop_column('devices', 'fbr_last_check')
    op.drop_column('devices', 'fbr_http_status')
    op.drop_column('devices', 'fbr_latency_ms')
    op.drop_column('devices', 'fbr_ok')
    op.drop_column('devices', 'fbr_status')
    op.drop_column('devices', 'clock_offset_sec')
    op.drop_column('devices', 'uptime_sec')
    op.drop_column('devices', 'utc_offset_minutes')
    op.drop_column('devices', 'timezone_name')
    op.drop_column('devices', 'utc_time')
    op.drop_column('devices', 'local_time')
