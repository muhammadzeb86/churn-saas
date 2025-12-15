"""add_production_indexes

Adds 4 essential database indexes for production performance:
1. idx_predictions_user_id - Tenant isolation queries
2. idx_predictions_created_at - Sorting/pagination
3. idx_predictions_user_created - Composite for user's recent predictions
4. idx_uploads_user_id - User upload history

Expected Performance Improvements:
- User predictions query: 500ms → 50ms (10x faster)
- Recent predictions: 300ms → 30ms (10x faster)
- Pagination: O(n) → O(log n)

Target Scale: 500 customers, 10K predictions/month

Revision ID: b4e2bb95fcb0
Revises: add_ml_training_data
Create Date: 2025-12-15 17:33:35.510220

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b4e2bb95fcb0'
down_revision = 'add_ml_training_data'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add 4 essential indexes for production
    
    Index Selection Rationale:
    --------------------------
    
    1. idx_predictions_user_id (Single column)
       Query: SELECT * FROM predictions WHERE user_id = 'clerk_user_123'
       Frequency: Every prediction list/detail request
       Without index: Full table scan (O(n))
       With index: Index seek (O(log n))
       
    2. idx_predictions_created_at (Single column)
       Query: SELECT * FROM predictions ORDER BY created_at DESC
       Frequency: Recent predictions, pagination
       Without index: Sort entire table (expensive)
       With index: Index scan (already sorted)
       
    3. idx_predictions_user_created (Composite)
       Query: SELECT * FROM predictions 
              WHERE user_id = 'X' 
              ORDER BY created_at DESC 
              LIMIT 10
       Frequency: User's recent predictions (most common query)
       Without index: Filter + sort (slow)
       With index: Single index scan (fast)
       
    4. idx_uploads_user_id (Single column)
       Query: SELECT * FROM uploads WHERE user_id = 'clerk_user_123'
       Frequency: Upload history, file management
       Without index: Full table scan
       With index: Index seek
    
    Index Maintenance Costs:
    ------------------------
    - Storage: ~10-20% of table size
    - Write speed: Marginal impact (we're read-heavy, 95% reads)
    - For 10K predictions: ~5MB index size (negligible)
    
    ROLLBACK SAFETY:
    ----------------
    Can safely rollback by dropping indexes.
    Queries still work, just slower.
    """
    
    # Index 1: predictions.user_id (tenant isolation)
    op.create_index(
        'idx_predictions_user_id',
        'predictions',
        ['user_id'],
        unique=False,
        postgresql_using='btree'
    )
    
    # Index 2: predictions.created_at (sorting/pagination)
    op.create_index(
        'idx_predictions_created_at',
        'predictions',
        ['created_at'],
        unique=False,
        postgresql_using='btree'
    )
    
    # Index 3: predictions(user_id, created_at) composite
    # Covers: "Get user's recent predictions" (most common query)
    op.create_index(
        'idx_predictions_user_created',
        'predictions',
        ['user_id', 'created_at'],
        unique=False,
        postgresql_using='btree'
    )
    
    # Index 4: uploads.user_id (upload history)
    op.create_index(
        'idx_uploads_user_id',
        'uploads',
        ['user_id'],
        unique=False,
        postgresql_using='btree'
    )
    
    # NOTE: We deliberately exclude these "nice-to-have" indexes for MVP:
    # - predictions.status (low cardinality, not worth indexing)
    # - predictions.id (already primary key, auto-indexed)
    # - uploads.status (low cardinality)
    # - full-text search (not needed yet, implement at 1000+ customers)


def downgrade() -> None:
    """
    Rollback: Drop all 4 indexes
    
    IMPACT:
    - Queries become slower (back to baseline performance)
    - No data loss
    - Application still functions normally
    
    WHEN TO ROLLBACK:
    - Index corruption (rare)
    - Performance regression (very rare)
    - Storage constraints (shouldn't happen at our scale)
    """
    op.drop_index('idx_uploads_user_id', table_name='uploads')
    op.drop_index('idx_predictions_user_created', table_name='predictions')
    op.drop_index('idx_predictions_created_at', table_name='predictions')
    op.drop_index('idx_predictions_user_id', table_name='predictions') 