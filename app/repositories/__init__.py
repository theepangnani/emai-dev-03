"""Repository layer for ClassBridge — data access abstractions over SQLAlchemy.

Each repository class provides named methods that encapsulate all SQLAlchemy
queries for a given domain model.  Route handlers depend on repositories
instead of writing raw ORM queries inline.

Usage:
    from app.repositories.task_repository import TaskRepository

    repo = TaskRepository(db)
    tasks = repo.list_for_user(current_user.id)

Or via FastAPI dependency injection (see app/api/deps.py):
    from app.api.deps import get_task_repo

    @router.get("/")
    def list_tasks(repo: TaskRepository = Depends(get_task_repo)):
        ...
"""

from app.repositories.base import BaseRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.course_content_repository import CourseContentRepository
from app.repositories.study_guide_repository import StudyGuideRepository

__all__ = [
    "BaseRepository",
    "TaskRepository",
    "CourseContentRepository",
    "StudyGuideRepository",
]
