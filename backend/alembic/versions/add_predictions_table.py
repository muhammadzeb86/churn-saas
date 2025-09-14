"""add predictions table with status enum and relationships

Revision ID: add_predictions_001
Revises: 0e12ce4eeec9
Create Date: 2025-09-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_predictions_001'
down_revision: Union[str, None] = '0e12ce4eeec9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    conn = op.get_bind()

    # 1) Create enum type if missing (safe re-run)
    op.execute("""
    DO backend/alembic/versions/add_predictions_table.py
    BEGIN
      IF NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'predictionstatus'
      ) THEN
        CREATE TYPE predictionstatus AS ENUM ('QUEUED','RUNNING','COMPLETED','FAILED');
      END IF;
    ENDbackend/alembic/versions/add_predictions_table.py;
    """)

    # 2) Create table only if it doesn't exist (safe re-run)
    exists = conn.dialect.has_table(conn, "predictions")
    if not exists:
        op.create_table(
            "predictions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("upload_id", sa.Integer(), sa.ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.String(255), index=True, nullable=False),
            sa.Column("status", sa.Enum("QUEUED","RUNNING","COMPLETED","FAILED", name="predictionstatus"), nullable=False, server_default="QUEUED"),
            sa.Column("s3_output_key", sa.String(1024), nullable=True),
            sa.Column("rows_processed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("metrics_json", sa.JSON(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        )
        op.create_index("ix_predictions_user_id", "predictions", ["user_id"])

def downgrade() -> None:
    # Drop table if exists (protect against partial states)
    conn = op.get_bind()
    exists = conn.dialect.has_table(conn, "predictions")
    if exists:
        op.drop_index("ix_predictions_user_id", table_name="predictions")
        op.drop_table("predictions")

    # Drop enum only if no columns still use it
    op.execute("""
    DO backend/alembic/versions/add_predictions_table.py
    BEGIN
      IF NOT EXISTS (
        SELECT 1
        FROM pg_attribute
        WHERE atttypid = 'predictionstatus'::regtype
      ) THEN
        DROP TYPE IF EXISTS predictionstatus;
      END IF;
    ENDbackend/alembic/versions/add_predictions_table.py;
    """)
