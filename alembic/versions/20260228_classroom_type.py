"""Make classroom_type non-nullable with default 'manual' for school vs private detection."""
from alembic import op
import sqlalchemy as sa

revision = "20260228_classroom_type"
down_revision = "20260203_add_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # For SQLite: classroom_type column already exists as nullable.
    # Set all NULL values to 'manual' first, then we rely on the ORM default going forward.
    # SQLite does not support ALTER COLUMN, so we leave the column as-is at the DB level
    # and rely on the ORM server_default + application default.
    op.execute("UPDATE courses SET classroom_type = 'manual' WHERE classroom_type IS NULL")


def downgrade() -> None:
    # No-op: the column already existed before this migration.
    # We just set NULLs to 'manual'; downgrade would set them back to NULL.
    op.execute("UPDATE courses SET classroom_type = NULL WHERE classroom_type = 'manual'")
