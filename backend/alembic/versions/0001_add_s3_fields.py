"""Add S3 fields to uploads table

Revision ID: 0001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add S3 object key column
    op.add_column('uploads', sa.Column('s3_object_key', sa.Text(), nullable=False, server_default=''))
    
    # Add file size column
    op.add_column('uploads', sa.Column('file_size', sa.Integer(), nullable=True))
    
    # Update existing records to have a default S3 object key
    op.execute("""
        UPDATE uploads 
        SET s3_object_key = CONCAT('uploads/', user_id, '/', filename) 
        WHERE s3_object_key = ''
    """)


def downgrade() -> None:
    # Remove the columns we added
    op.drop_column('uploads', 'file_size')
    op.drop_column('uploads', 's3_object_key') 