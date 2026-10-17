"""initial schema with alert rules

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-10-13 08:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('failed_login_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)

    # 2. stores
    op.create_table(
        'stores',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('region', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_stores_id'), 'stores', ['id'], unique=False)
    op.create_index(op.f('ix_stores_code'), 'stores', ['code'], unique=True)

    # 3. user_stores
    op.create_table(
        'user_stores',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('store_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_user_stores_user_store', 'user_stores', ['user_id', 'store_id'], unique=True)

    # 4. enrollment_keys
    op.create_table(
        'enrollment_keys',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('store_id', sa.Integer(), nullable=False),
        sa.Column('key_hash', sa.String(length=255), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_enrollment_keys_id'), 'enrollment_keys', ['id'], unique=False)
    op.create_index(op.f('ix_enrollment_keys_key_hash'), 'enrollment_keys', ['key_hash'], unique=False)

    # 5. devices
    op.create_table(
        'devices',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('device_id', sa.String(length=100), nullable=False),
        sa.Column('computer_name', sa.String(length=150), nullable=False),
        sa.Column('store_id', sa.Integer(), nullable=False),
        sa.Column('device_type', sa.String(length=30), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=False),
        sa.Column('os_version', sa.String(length=150), nullable=False),
        sa.Column('agent_version', sa.String(length=50), nullable=False),
        sa.Column('token_hash', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=False),
        sa.Column('registered_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_devices_device_id'), 'devices', ['device_id'], unique=True)
    op.create_index(op.f('ix_devices_token_hash'), 'devices', ['token_hash'], unique=False)

    # 6. alert_rules
    op.create_table(
        'alert_rules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('rule_key', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('threshold_value', sa.Float(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alert_rules_id'), 'alert_rules', ['id'], unique=False)
    op.create_index(op.f('ix_alert_rules_rule_key'), 'alert_rules', ['rule_key'], unique=True)

    # 7. metrics
    op.create_table(
        'metrics',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('device_pk', sa.String(length=36), nullable=False),
        sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('cpu_pct', sa.Float(), nullable=False),
        sa.Column('ram_pct', sa.Float(), nullable=False),
        sa.Column('ram_used_mb', sa.Float(), nullable=False),
        sa.Column('disk_json', sa.JSON(), nullable=False),
        sa.Column('net_json', sa.JSON(), nullable=False),
        sa.Column('internet_ok', sa.Boolean(), nullable=False),
        sa.Column('printers_json', sa.JSON(), nullable=True),
        sa.Column('services_json', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['device_pk'], ['devices.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_metrics_device_ts', 'metrics', ['device_pk', 'ts'], unique=False)

    # 8. alerts
    op.create_table(
        'alerts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('device_pk', sa.String(length=36), nullable=False),
        sa.Column('rule_key', sa.String(length=100), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('state', sa.String(length=20), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('value', sa.String(length=100), nullable=True),
        sa.Column('fired_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('acked_by', sa.Integer(), nullable=True),
        sa.Column('acked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['acked_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['device_pk'], ['devices.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alerts_device_pk'), 'alerts', ['device_pk'], unique=False)
    op.create_index(op.f('ix_alerts_rule_key'), 'alerts', ['rule_key'], unique=False)

    # 9. notes
    op.create_table(
        'notes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('device_pk', sa.String(length=36), nullable=False),
        sa.Column('alert_id', sa.Integer(), nullable=True),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['alert_id'], ['alerts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['device_pk'], ['devices.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 10. audit_logs
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('actor_type', sa.String(length=20), nullable=False),
        sa.Column('actor', sa.String(length=150), nullable=False),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('target', sa.String(length=150), nullable=True),
        sa.Column('ip', sa.String(length=45), nullable=True),
        sa.Column('detail_json', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_ts'), 'audit_logs', ['ts'], unique=False)


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('notes')
    op.drop_table('alerts')
    op.drop_table('metrics')
    op.drop_table('alert_rules')
    op.drop_table('devices')
    op.drop_table('enrollment_keys')
    op.drop_table('user_stores')
    op.drop_table('stores')
    op.drop_table('users')
