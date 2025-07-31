"""Add Clerk fields to users table

Revision ID: 0003
Revises: 0002
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None

def upgrade():
    # Add Clerk-specific columns to users table
    op.add_column('users', sa.Column('clerk_id', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('first_name', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('last_name', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('avatar_url', sa.Text(), nullable=True))
    
    # Create unique index on clerk_id
    op.create_index('ix_users_clerk_id', 'users', ['clerk_id'], unique=True)
    
    # Make clerk_id not null after adding the column
    # Note: This will fail if there are existing users without clerk_id
    # In production, you'd need to handle this migration more carefully
    op.alter_column('users', 'clerk_id', nullable=False)

def downgrade():
    # Drop the unique index
    op.drop_index('ix_users_clerk_id', table_name='users')
    
    # Drop the columns
    op.drop_column('users', 'avatar_url')
    op.drop_column('users', 'last_name')
    op.drop_column('users', 'first_name')
    op.drop_column('users', 'clerk_id') 