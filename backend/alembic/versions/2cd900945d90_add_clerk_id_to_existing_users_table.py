"""Add clerk_id to existing users table

Revision ID: 2cd900945d90
Revises: 0e12ce4eeec9
Create Date: 2025-08-03 22:20:15.123456

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2cd900945d90'
down_revision = '0e12ce4eeec9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add clerk_id column to existing users table
    op.add_column('users', sa.Column('clerk_id', sa.String(length=255), nullable=True))
    
    # Add other missing columns if they don't exist
    op.add_column('users', sa.Column('first_name', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('last_name', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('avatar_url', sa.Text(), nullable=True))
    
    # Create unique constraint on clerk_id
    op.create_unique_constraint('uq_users_clerk_id', 'users', ['clerk_id'])


def downgrade() -> None:
    # Remove the unique constraint
    op.drop_constraint('uq_users_clerk_id', 'users', type_='unique')
    
    # Drop the columns
    op.drop_column('users', 'avatar_url')
    op.drop_column('users', 'last_name')
    op.drop_column('users', 'first_name')
    op.drop_column('users', 'clerk_id') 