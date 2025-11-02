"""Add SQS metadata columns to predictions table

Revision ID: add_sqs_metadata
Revises: add_predictions_table
Create Date: 2025-11-02 12:00:00.000000

Task 1.1: SQS Queue Configuration
Adds sqs_message_id and sqs_queued_at columns for tracking SQS message lifecycle
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_sqs_metadata'
down_revision = 'add_predictions_001'  # Points to actual revision ID
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add SQS metadata columns to predictions table"""
    # Check if columns already exist before adding
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    if inspector.has_table("predictions"):
        columns = [col['name'] for col in inspector.get_columns("predictions")]
        
        # Add sqs_message_id if not exists
        if 'sqs_message_id' not in columns:
            op.add_column(
                'predictions',
                sa.Column(
                    'sqs_message_id',
                    sa.String(255),
                    nullable=True,
                    comment='SQS MessageId for tracking'
                )
            )
            print("✅ Added column: sqs_message_id")
        else:
            print("⏭️  Column already exists: sqs_message_id")
        
        # Add sqs_queued_at if not exists
        if 'sqs_queued_at' not in columns:
            op.add_column(
                'predictions',
                sa.Column(
                    'sqs_queued_at',
                    sa.DateTime(timezone=True),
                    nullable=True,
                    comment='When message was published to SQS'
                )
            )
            print("✅ Added column: sqs_queued_at")
        else:
            print("⏭️  Column already exists: sqs_queued_at")
    else:
        print("⚠️  Table 'predictions' does not exist - skipping migration")


def downgrade() -> None:
    """Remove SQS metadata columns from predictions table"""
    # Check if columns exist before dropping
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    if inspector.has_table("predictions"):
        columns = [col['name'] for col in inspector.get_columns("predictions")]
        
        if 'sqs_queued_at' in columns:
            op.drop_column('predictions', 'sqs_queued_at')
            print("✅ Dropped column: sqs_queued_at")
        
        if 'sqs_message_id' in columns:
            op.drop_column('predictions', 'sqs_message_id')
            print("✅ Dropped column: sqs_message_id")
    else:
        print("⚠️  Table 'predictions' does not exist - skipping downgrade")

