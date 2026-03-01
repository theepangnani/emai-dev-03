"""Base repository providing generic CRUD operations for SQLAlchemy models."""

from typing import TypeVar, Generic, Type, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Generic repository that provides basic CRUD operations.

    Subclass this and call ``super().__init__(MyModel, db)`` to inherit
    the standard get / get_all / create / delete helpers.

    Transaction management (commit/rollback) stays in the route handlers;
    repositories use ``db.flush()`` to make IDs available before commit.
    """

    def __init__(self, model: Type[ModelType], db: Session) -> None:
        self.model = model
        self.db = db

    def get(self, id: int) -> ModelType | None:
        """Fetch a single record by primary key.  Returns None if not found."""
        return self.db.get(self.model, id)

    def get_all(self, *, limit: int = 100, offset: int = 0) -> Sequence[ModelType]:
        """Return all records with optional pagination.  No access filtering."""
        return self.db.execute(
            select(self.model).limit(limit).offset(offset)
        ).scalars().all()

    def create(self, obj: ModelType) -> ModelType:
        """Persist a new model instance and flush to obtain its auto-generated ID.

        The caller is responsible for committing the enclosing transaction.
        """
        self.db.add(obj)
        self.db.flush()
        self.db.refresh(obj)
        return obj

    def delete(self, obj: ModelType) -> None:
        """Hard-delete a model instance and flush.

        The caller is responsible for committing the enclosing transaction.
        """
        self.db.delete(obj)
        self.db.flush()
