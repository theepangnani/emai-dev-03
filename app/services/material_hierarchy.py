"""Service layer for material hierarchy (master/sub) operations (#1740)."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session
from app.core.logging_config import get_logger

if TYPE_CHECKING:
    from app.models.course_content import CourseContent

logger = get_logger(__name__)


def _get_model():
    """Lazy import CourseContent to avoid stale references in test environments."""
    from app.models.course_content import CourseContent
    return CourseContent


def create_material_hierarchy(
    db: Session,
    master_content: CourseContent,
    sub_contents: list[CourseContent],
) -> int:
    """Link a master material with its sub-materials using a shared group ID.

    Args:
        db: Database session
        master_content: The master CourseContent (already added to session)
        sub_contents: List of sub CourseContent objects (already added to session)

    Returns:
        The material_group_id assigned to the group
    """
    # Use timestamp-based group ID (unique enough for our purposes)
    group_id = int(time.time() * 1000) % 2147483647  # Keep within INT range

    master_content.is_master = "true"
    master_content.material_group_id = group_id
    master_content.parent_content_id = None  # Master has no parent

    for sub in sub_contents:
        sub.parent_content_id = master_content.id
        sub.is_master = "false"
        sub.material_group_id = group_id

    logger.info(
        "Created material hierarchy: master=%d, subs=%d, group=%d",
        master_content.id,
        len(sub_contents),
        group_id,
    )
    return group_id


def get_linked_materials(db: Session, content_id: int) -> list[CourseContent]:
    """Get all materials linked to the given content (master + siblings).

    If the content is a master: returns all sub-materials.
    If the content is a sub: returns the master + all sibling subs.
    If standalone (no group): returns empty list.
    """
    CourseContent = _get_model()

    content = db.query(CourseContent).filter(
        CourseContent.id == content_id,
        CourseContent.archived_at.is_(None),
    ).first()

    if not content or not content.material_group_id:
        return []

    # Get all materials in the same group, excluding the current one
    linked = db.query(CourseContent).filter(
        CourseContent.material_group_id == content.material_group_id,
        CourseContent.id != content_id,
        CourseContent.archived_at.is_(None),
    ).order_by(
        CourseContent.is_master.desc(),  # Master first
        CourseContent.id.asc(),  # Then by creation order
    ).all()

    return linked


def generate_sub_title(master_title: str, part_number: int) -> str:
    """Generate a sub-material title from the master title.

    Example: "Math Notes" -> "Math Notes — Part 1"
    """
    return f"{master_title} \u2014 Part {part_number}"
