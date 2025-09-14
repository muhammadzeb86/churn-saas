"""add foreign key constraint to predictions.user_id

Revision ID: add_user_fk_001
Revises: add_predictions_001
Create Date: 2025-09-14 20:56:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'add_user_fk_001'
down_revision: Union[str, None] = 'add_predictions_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Add foreign key constraint to user_id column
    op.create_foreign_key(
        'fk_predictions_user_id',  # constraint name
        'predictions',  # source table
        'users',  # target table
        ['user_id'],  # source columns
        ['id'],  # target columns
        ondelete='CASCADE'
    )

def downgrade() -> None:
    # Drop the foreign key constraint
    op.drop_constraint('fk_predictions_user_id', 'predictions', type_='foreignkey') 