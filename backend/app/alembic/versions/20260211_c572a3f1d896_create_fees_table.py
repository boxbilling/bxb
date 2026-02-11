"""create_fees_table

Revision ID: c572a3f1d896
Revises: b461931de855
Create Date: 2026-02-11 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c572a3f1d896'
down_revision = 'b461931de855'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('fees',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('invoice_id', sa.String(length=36), nullable=True),
        sa.Column('charge_id', sa.String(length=36), nullable=True),
        sa.Column('subscription_id', sa.String(length=36), nullable=True),
        sa.Column('customer_id', sa.String(length=36), nullable=False),
        sa.Column('fee_type', sa.String(length=20), nullable=False),
        sa.Column('amount_cents', sa.Numeric(precision=12, scale=4), nullable=False, server_default='0'),
        sa.Column('taxes_amount_cents', sa.Numeric(precision=12, scale=4), nullable=False, server_default='0'),
        sa.Column('total_amount_cents', sa.Numeric(precision=12, scale=4), nullable=False, server_default='0'),
        sa.Column('units', sa.Numeric(precision=12, scale=4), nullable=False, server_default='0'),
        sa.Column('events_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('unit_amount_cents', sa.Numeric(precision=12, scale=4), nullable=False, server_default='0'),
        sa.Column('payment_status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('metric_code', sa.String(length=255), nullable=True),
        sa.Column('properties', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['charge_id'], ['charges.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_fees_invoice_id', 'fees', ['invoice_id'], unique=False)
    op.create_index('ix_fees_customer_id', 'fees', ['customer_id'], unique=False)
    op.create_index('ix_fees_subscription_id', 'fees', ['subscription_id'], unique=False)
    op.create_index('ix_fees_charge_id', 'fees', ['charge_id'], unique=False)
    op.create_index('ix_fees_fee_type', 'fees', ['fee_type'], unique=False)


def downgrade():
    op.drop_index('ix_fees_fee_type', table_name='fees')
    op.drop_index('ix_fees_charge_id', table_name='fees')
    op.drop_index('ix_fees_subscription_id', table_name='fees')
    op.drop_index('ix_fees_customer_id', table_name='fees')
    op.drop_index('ix_fees_invoice_id', table_name='fees')
    op.drop_table('fees')
