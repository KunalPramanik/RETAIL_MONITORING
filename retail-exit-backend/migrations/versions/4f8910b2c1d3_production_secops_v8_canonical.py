"""SEC-OPS V8 Canonical Platform Migration

Revision ID: 4f8910b2c1d3
Revises: 3a419bf4a775
Create Date: 2026-10-15 19:49:00.000000

Non-destructive upgrade ensuring platform control-plane tables exist
with full compatibility across PostgreSQL and SQLite.
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '4f8910b2c1d3'
down_revision: Union[str, Sequence[str], None] = '3a419bf4a775'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. platform_tenant
    op.create_table(
        'platform_tenant',
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=64), nullable=False),
        sa.Column('db_identifier', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=32), server_default='PROVISIONING', nullable=False),
        sa.Column('timezone', sa.String(length=64), server_default='Asia/Kolkata', nullable=False),
        sa.Column('currency', sa.String(length=16), server_default='INR', nullable=False),
        sa.Column('contact_email', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('tenant_id'),
        sa.UniqueConstraint('db_identifier'),
        sa.UniqueConstraint('name'),
        sa.UniqueConstraint('slug'),
    )
    op.create_index('idx_platform_tenant_status', 'platform_tenant', ['status'], unique=False)

    # 2. platform_super_admin
    op.create_table(
        'platform_super_admin',
        sa.Column('admin_id', sa.String(length=36), nullable=False),
        sa.Column('username', sa.String(length=64), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=32), server_default='SUPER_ADMIN', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('admin_id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username'),
    )
    op.create_index('idx_platform_super_admin_email', 'platform_super_admin', ['email'], unique=False)

    # 3. platform_subscription_tier
    op.create_table(
        'platform_subscription_tier',
        sa.Column('tier_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('max_cameras', sa.Integer(), server_default='4', nullable=False),
        sa.Column('price_cents', sa.Integer(), server_default='0', nullable=False),
        sa.Column('currency', sa.String(length=16), server_default='INR', nullable=False),
        sa.Column('billing_cycle', sa.String(length=16), server_default='MONTHLY', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('tier_id'),
        sa.UniqueConstraint('name'),
    )

    # 4. platform_store_subscription
    op.create_table(
        'platform_store_subscription',
        sa.Column('subscription_id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('tier_id', sa.String(length=36), nullable=False),
        sa.Column('status', sa.String(length=32), server_default='ACTIVE', nullable=False),
        sa.Column('current_period_start', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('grace_period_days', sa.Integer(), server_default='7', nullable=False),
        sa.Column('payment_verified', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('auto_renew', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('last_payment_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('subscription_id'),
        sa.UniqueConstraint('tenant_id'),
    )
    op.create_index('idx_platform_sub_tenant', 'platform_store_subscription', ['tenant_id'], unique=False)
    op.create_index('idx_platform_sub_status', 'platform_store_subscription', ['status'], unique=False)

    # 5. platform_billing_invoice
    op.create_table(
        'platform_billing_invoice',
        sa.Column('invoice_id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=False),
        sa.Column('subscription_id', sa.String(length=36), nullable=True),
        sa.Column('amount_cents', sa.Integer(), server_default='0', nullable=False),
        sa.Column('currency', sa.String(length=16), server_default='INR', nullable=False),
        sa.Column('status', sa.String(length=32), server_default='PAID', nullable=False),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('payment_reference', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('invoice_id'),
    )
    op.create_index('idx_platform_inv_tenant', 'platform_billing_invoice', ['tenant_id'], unique=False)
    op.create_index('idx_platform_inv_status', 'platform_billing_invoice', ['status'], unique=False)

    # 6. platform_audit_log
    op.create_table(
        'platform_audit_log',
        sa.Column('log_id', sa.String(length=36), nullable=False),
        sa.Column('actor_id', sa.String(length=36), nullable=False),
        sa.Column('actor_type', sa.String(length=32), server_default='SUPER_ADMIN', nullable=False),
        sa.Column('action', sa.String(length=64), nullable=False),
        sa.Column('tenant_id', sa.String(length=36), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('log_id'),
    )
    op.create_index('idx_platform_audit_created', 'platform_audit_log', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_platform_audit_created', table_name='platform_audit_log')
    op.drop_table('platform_audit_log')
    op.drop_index('idx_platform_inv_status', table_name='platform_billing_invoice')
    op.drop_index('idx_platform_inv_tenant', table_name='platform_billing_invoice')
    op.drop_table('platform_billing_invoice')
    op.drop_index('idx_platform_sub_status', table_name='platform_store_subscription')
    op.drop_index('idx_platform_sub_tenant', table_name='platform_store_subscription')
    op.drop_table('platform_store_subscription')
    op.drop_table('platform_subscription_tier')
    op.drop_index('idx_platform_super_admin_email', table_name='platform_super_admin')
    op.drop_table('platform_super_admin')
    op.drop_index('idx_platform_tenant_status', table_name='platform_tenant')
    op.drop_table('platform_tenant')
