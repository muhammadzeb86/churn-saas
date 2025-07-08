"""Add waitlist_emails table

Revision ID: 002
Revises: 001
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create waitlist_emails table
    op.create_table('waitlist_emails',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create unique index on email
    op.create_index(op.f('ix_waitlist_emails_email'), 'waitlist_emails', ['email'], unique=True)
    op.create_index(op.f('ix_waitlist_emails_id'), 'waitlist_emails', ['id'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_waitlist_emails_id'), table_name='waitlist_emails')
    op.drop_index(op.f('ix_waitlist_emails_email'), table_name='waitlist_emails')
    
    # Drop table
    op.drop_table('waitlist_emails') 