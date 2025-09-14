"""add predictions table with status enum and relationships

Revision ID: add_predictions_001
Revises: 0e12ce4eeec9
Create Date: 2025-09-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_predictions_001'
down_revision: Union[str, None] = '0e12ce4eeec9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Create enum type
prediction_status_enum = postgresql.ENUM('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', name='predictionstatus')

def upgrade() -> None:
    # Create enum type
    prediction_status_enum.create(op.get_bind(), checkfirst=True)
    
    # Create predictions table
    op.create_table('predictions',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('upload_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.String(length=255), nullable=False),
    sa.Column('status', prediction_status_enum, nullable=False),
    sa.Column('s3_output_key', sa.String(length=1024), nullable=True),
    sa.Column('rows_processed', sa.Integer(), nullable=False),
    sa.Column('metrics_json', sa.JSON(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['upload_id'], ['uploads.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index(op.f('ix_predictions_user_id'), 'predictions', ['user_id'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_predictions_user_id'), table_name='predictions')
    
    # Drop table
    op.drop_table('predictions')
    
    # Drop enum type
    prediction_status_enum.drop(op.get_bind(), checkfirst=True) 
