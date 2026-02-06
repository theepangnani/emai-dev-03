"""Add performance indexes for messages, notifications, and related tables."""
from alembic import op

revision = "20260203_add_indexes"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_conversations_participants",
        "conversations",
        ["participant_1_id", "participant_2_id"],
    )
    op.create_index(
        "ix_conversations_student",
        "conversations",
        ["student_id"],
    )
    op.create_index(
        "ix_messages_conversation_created",
        "messages",
        ["conversation_id", "created_at"],
    )
    op.create_index(
        "ix_messages_conversation_read",
        "messages",
        ["conversation_id", "is_read"],
    )
    op.create_index(
        "ix_messages_sender_created",
        "messages",
        ["sender_id", "created_at"],
    )
    op.create_index(
        "ix_notifications_user_read_created",
        "notifications",
        ["user_id", "read", "created_at"],
    )
    op.create_index(
        "ix_assignments_course_due",
        "assignments",
        ["course_id", "due_date"],
    )
    op.create_index(
        "ix_student_assignments_student",
        "student_assignments",
        ["student_id"],
    )
    op.create_index(
        "ix_student_assignments_assignment",
        "student_assignments",
        ["assignment_id"],
    )
    op.create_index(
        "ix_courses_teacher",
        "courses",
        ["teacher_id"],
    )
    op.create_index(
        "ix_students_user",
        "students",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_students_user", table_name="students")
    op.drop_index("ix_courses_teacher", table_name="courses")
    op.drop_index("ix_student_assignments_assignment", table_name="student_assignments")
    op.drop_index("ix_student_assignments_student", table_name="student_assignments")
    op.drop_index("ix_assignments_course_due", table_name="assignments")
    op.drop_index("ix_notifications_user_read_created", table_name="notifications")
    op.drop_index("ix_messages_sender_created", table_name="messages")
    op.drop_index("ix_messages_conversation_read", table_name="messages")
    op.drop_index("ix_messages_conversation_created", table_name="messages")
    op.drop_index("ix_conversations_student", table_name="conversations")
    op.drop_index("ix_conversations_participants", table_name="conversations")
