"""add foreign key constraint to predictions.user_id

Revision ID: add_user_fk_constraint
Revises: add_predictions_001
Create Date: 2025-09-14 21:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'add_user_fk_constraint'
down_revision: Union[str, None] = 'add_predictions_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Add foreign key constraint idempotently
    op.execute("""
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_predictions_user_id_users'
      ) THEN
        ALTER TABLE predictions
        ADD CONSTRAINT fk_predictions_user_id_users
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE;
      END IF;
    END$$;
    """)

def downgrade() -> None:
    # Drop the foreign key constraint idempotently
    op.execute("""
    DO $$
    BEGIN
      IF EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_predictions_user_id_users'
      ) THEN
        ALTER TABLE predictions DROP CONSTRAINT fk_predictions_user_id_users;
      END IF;
    END$$;
    """) 