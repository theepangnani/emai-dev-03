"""Add student_emails table for email identity merging."""
import sqlalchemy as sa
from alembic import op

revision = "20260228_student_emails"
down_revision = "20260203_add_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "student_emails",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "student_id",
            sa.Integer(),
            sa.ForeignKey("students.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column(
            "email_type",
            sa.Enum("personal", "school", name="emailtype"),
            nullable=False,
            server_default="personal",
        ),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("student_id", "email", name="uq_student_emails_pair"),
    )
    op.create_index("ix_student_emails_student", "student_emails", ["student_id"])
    op.create_index("ix_student_emails_email", "student_emails", ["email"])


def downgrade() -> None:
    op.drop_index("ix_student_emails_email", table_name="student_emails")
    op.drop_index("ix_student_emails_student", table_name="student_emails")
    op.drop_table("student_emails")
