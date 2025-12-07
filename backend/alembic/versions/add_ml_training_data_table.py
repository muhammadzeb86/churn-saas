"""add ml_training_data table for real data collection

Revision ID: add_ml_training_data
Revises: add_sqs_metadata_to_predictions
Create Date: 2025-12-07 21:30:00.000000

This table stores predictions and actual churn outcomes for future ML model training.
Part of Task 1.7: SaaS Baseline + Real Data Collection.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_ml_training_data'
down_revision: Union[str, None] = 'add_sqs_metadata_to_predictions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create ml_training_data table for collecting real customer data and outcomes.
    
    This table is the foundation for training ML models on REAL data (not synthetic).
    It stores:
    - Every prediction with full customer features
    - Actual churn outcomes when known
    - Experiment group assignment (A/B testing)
    """
    conn = op.get_bind()
    
    # Create table only if missing
    if not conn.dialect.has_table(conn, "ml_training_data"):
        op.create_table(
            "ml_training_data",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            
            # Customer info
            sa.Column("customer_id", sa.String(100), nullable=False),
            sa.Column("prediction_id", sa.String(100), nullable=True),
            
            # Features (at time of prediction) - stored as JSON
            sa.Column("features_json", postgresql.JSON, nullable=False),
            
            # Prediction results
            sa.Column("predicted_churn_prob", sa.Float(), nullable=False),
            sa.Column("predicted_retention_prob", sa.Float(), nullable=False),
            sa.Column("model_type", sa.String(50), nullable=False),  # 'telecom', 'saas_baseline', etc.
            sa.Column("experiment_group", sa.String(20), nullable=True),  # 'control', 'treatment'
            
            # Actual outcome (filled in later when customer churns/stays)
            sa.Column("actual_churned", sa.Boolean(), nullable=True),
            sa.Column("outcome_recorded_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("days_to_outcome", sa.Integer(), nullable=True),  # Days from prediction to outcome
            
            # Timestamps
            sa.Column("predicted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        )
        
        # Create indexes for common queries
        op.create_index(
            "ix_ml_training_data_customer_id",
            "ml_training_data",
            ["customer_id"],
            unique=False
        )
        
        op.create_index(
            "ix_ml_training_data_prediction_id",
            "ml_training_data",
            ["prediction_id"],
            unique=False
        )
        
        op.create_index(
            "ix_ml_training_data_actual_churned",
            "ml_training_data",
            ["actual_churned"],
            unique=False,
            postgresql_where=sa.text("actual_churned IS NOT NULL")
        )
        
        op.create_index(
            "ix_ml_training_data_predicted_at",
            "ml_training_data",
            ["predicted_at"],
            unique=False
        )
        
        op.create_index(
            "ix_ml_training_data_model_type",
            "ml_training_data",
            ["model_type"],
            unique=False
        )
        
        print("✅ Created ml_training_data table with indexes")


def downgrade() -> None:
    """Drop ml_training_data table and all indexes."""
    conn = op.get_bind()
    
    if conn.dialect.has_table(conn, "ml_training_data"):
        # Drop indexes first
        op.drop_index("ix_ml_training_data_model_type", table_name="ml_training_data")
        op.drop_index("ix_ml_training_data_predicted_at", table_name="ml_training_data")
        op.drop_index("ix_ml_training_data_actual_churned", table_name="ml_training_data")
        op.drop_index("ix_ml_training_data_prediction_id", table_name="ml_training_data")
        op.drop_index("ix_ml_training_data_customer_id", table_name="ml_training_data")
        
        # Drop table
        op.drop_table("ml_training_data")
        
        print("✅ Dropped ml_training_data table and indexes")

