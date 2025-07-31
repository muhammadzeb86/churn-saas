"""Create leads table

Revision ID: 0002
Revises: 0001
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None

def upgrade():
    # Create leads table
    op.create_table('leads',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('source', sa.String(length=100), nullable=True),
        sa.Column('converted_to_user', sa.Boolean(), nullable=False, default=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    
    # Create index on email
    op.create_index('ix_leads_email', 'leads', ['email'])

def downgrade():
    # Drop index
    op.drop_index('ix_leads_email', table_name='leads')
    
    # Drop leads table
    op.drop_table('leads') 