"""fbr registrations and invoices

Revision ID: 0004_fbr_registrations_and_invoices
Revises: 0003_agent_tasks_and_state
Create Date: 2026-10-16 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0004_fbr_registrations_and_invoices'
down_revision: Union[str, None] = '0003_agent_tasks_and_state'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Add FBR & IMS separation columns to devices
    with op.batch_alter_table('devices') as batch_op:
        batch_op.add_column(sa.Column('fbr_pos_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('fbr_pos_identification', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('local_ims_status', sa.String(length=50), server_default='UNKNOWN', nullable=False))
        batch_op.add_column(sa.Column('fbr_connectivity_status', sa.String(length=50), server_default='UNKNOWN', nullable=False))
        batch_op.add_column(sa.Column('last_fiscal_sync', sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index('ix_devices_fbr_pos_id', ['fbr_pos_id'], unique=False)

    # 2. Create fbr_registrations table
    op.create_table(
        'fbr_registrations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('fbr_pos_id', sa.Integer(), nullable=False),
        sa.Column('pos_identification', sa.String(length=100), nullable=False),
        sa.Column('branch_name', sa.String(length=150), nullable=False),
        sa.Column('store_code', sa.String(length=30), nullable=True),
        sa.Column('store_id', sa.Integer(), nullable=True),
        sa.Column('device_pk', sa.String(length=36), nullable=True),
        sa.Column('portal_status', sa.String(length=50), server_default='Connected', nullable=False),
        sa.Column('connected_date', sa.String(length=50), nullable=True),
        sa.Column('code', sa.String(length=50), nullable=True),
        sa.Column('pos_software_version', sa.String(length=50), nullable=True),
        sa.Column('is_unidentified', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('token_configured', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('admin_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['device_pk'], ['devices.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('fbr_pos_id', name='uq_fbr_registrations_pos_id')
    )
    op.create_index('ix_fbr_registrations_fbr_pos_id', 'fbr_registrations', ['fbr_pos_id'], unique=True)
    op.create_index('ix_fbr_registrations_pos_identification', 'fbr_registrations', ['pos_identification'], unique=False)
    op.create_index('ix_fbr_registrations_branch_name', 'fbr_registrations', ['branch_name'], unique=False)
    op.create_index('ix_fbr_registrations_store_id', 'fbr_registrations', ['store_id'], unique=False)
    op.create_index('ix_fbr_registrations_device_pk', 'fbr_registrations', ['device_pk'], unique=False)

    # 3. Create pos_invoices table
    op.create_table(
        'pos_invoices',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('internal_invoice_id', sa.String(length=100), nullable=False),
        sa.Column('original_invoice_no', sa.String(length=100), nullable=False),
        sa.Column('store_id', sa.Integer(), nullable=False),
        sa.Column('device_pk', sa.String(length=36), nullable=False),
        sa.Column('fbr_pos_id', sa.Integer(), nullable=True),
        sa.Column('invoice_datetime', sa.DateTime(timezone=True), nullable=False),
        sa.Column('total_amount', sa.Float(), nullable=True),
        sa.Column('tax_amount', sa.Float(), nullable=True),
        sa.Column('currency', sa.String(length=10), server_default='PKR', nullable=False),
        sa.Column('fiscal_status', sa.String(length=40), server_default='PENDING', nullable=False),
        sa.Column('fbr_invoice_number', sa.String(length=100), nullable=True),
        sa.Column('qr_code', sa.Text(), nullable=True),
        sa.Column('attempts_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_response_code', sa.Integer(), nullable=True),
        sa.Column('last_response_text', sa.Text(), nullable=True),
        sa.Column('is_retry_eligible', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('reconciliation_status', sa.String(length=50), server_default='NOT_RECONCILED', nullable=False),
        sa.Column('blocked_reason', sa.String(length=255), nullable=True),
        sa.Column('active_retry_task_id', sa.Integer(), nullable=True),
        sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('locked_by', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['device_pk'], ['devices.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('internal_invoice_id', name='uq_pos_invoices_internal_id'),
        sa.UniqueConstraint('original_invoice_no', name='uq_pos_invoices_original_no')
    )
    op.create_index('ix_pos_invoices_internal_id', 'pos_invoices', ['internal_invoice_id'], unique=True)
    op.create_index('ix_pos_invoices_original_no', 'pos_invoices', ['original_invoice_no'], unique=True)
    op.create_index('ix_pos_invoices_store_id', 'pos_invoices', ['store_id'], unique=False)
    op.create_index('ix_pos_invoices_device_pk', 'pos_invoices', ['device_pk'], unique=False)
    op.create_index('ix_pos_invoices_fiscal_status', 'pos_invoices', ['fiscal_status'], unique=False)
    op.create_index('ix_pos_invoices_fbr_invoice_number', 'pos_invoices', ['fbr_invoice_number'], unique=False)
    op.create_index('ix_pos_invoices_datetime', 'pos_invoices', ['invoice_datetime'], unique=False)

    # 4. Create invoice_fiscal_attempts table
    op.create_table(
        'invoice_fiscal_attempts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('invoice_id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=True),
        sa.Column('attempt_number', sa.Integer(), nullable=False),
        sa.Column('attempt_type', sa.String(length=30), server_default='MANUAL_RETRY', nullable=False),
        sa.Column('initiated_by', sa.String(length=100), nullable=False),
        sa.Column('initiated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('request_payload_json', sa.JSON(), nullable=True),
        sa.Column('response_code', sa.Integer(), nullable=True),
        sa.Column('response_body_text', sa.Text(), nullable=True),
        sa.Column('outcome', sa.String(length=40), nullable=False),
        sa.Column('fbr_invoice_number', sa.String(length=100), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['invoice_id'], ['pos_invoices.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_invoice_attempts_invoice_id', 'invoice_fiscal_attempts', ['invoice_id'], unique=False)

    # 5. Create cco_integration_configs table
    op.create_table(
        'cco_integration_configs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('store_id', sa.Integer(), nullable=False),
        sa.Column('cco_install_path', sa.String(length=255), server_default=r'C:\SapCustomerCheckout\cco', nullable=False),
        sa.Column('cco_derby_path', sa.String(length=255), server_default=r'C:\SapCustomerCheckout\cco\db\CCO', nullable=False),
        sa.Column('export_folder', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), server_default='INVOICE SOURCE NOT CONFIGURED', nullable=False),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_sync_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('store_id', name='uq_cco_integration_store')
    )

def downgrade() -> None:
    op.drop_table('cco_integration_configs')
    op.drop_table('invoice_fiscal_attempts')
    op.drop_table('pos_invoices')
    op.drop_table('fbr_registrations')
    with op.batch_alter_table('devices') as batch_op:
        batch_op.drop_index('ix_devices_fbr_pos_id')
        batch_op.drop_column('last_fiscal_sync')
        batch_op.drop_column('fbr_connectivity_status')
        batch_op.drop_column('local_ims_status')
        batch_op.drop_column('fbr_pos_identification')
        batch_op.drop_column('fbr_pos_id')
