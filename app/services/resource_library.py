"""Service layer for the Teacher Resource Library."""
import json
import logging
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from fastapi import HTTPException, status

from app.models.resource_library import TeacherResource, ResourceRating, ResourceCollection
from app.models.lesson_plan import LessonPlan, LessonPlanType
from app.models.teacher import Teacher
from app.schemas.resource_library import (
    TeacherResourceCreate,
    TeacherResourceUpdate,
    ResourceSearchParams,
)

logger = logging.getLogger(__name__)


def _serialize_tags(tags: Optional[List[str]]) -> Optional[str]:
    if tags is None:
        return None
    return json.dumps(tags)


def _deserialize_tags(tags_json: Optional[str]) -> List[str]:
    if not tags_json:
        return []
    try:
        result = json.loads(tags_json)
        return result if isinstance(result, list) else []
    except Exception:
        return []


def _serialize_resource_ids(ids: Optional[List[int]]) -> str:
    if not ids:
        return "[]"
    return json.dumps(ids)


def _deserialize_resource_ids(ids_json: Optional[str]) -> List[int]:
    if not ids_json:
        return []
    try:
        result = json.loads(ids_json)
        return result if isinstance(result, list) else []
    except Exception:
        return []


def _resource_to_dict(resource: TeacherResource, teacher_name: Optional[str] = None) -> dict:
    """Convert a TeacherResource ORM object to a response dict."""
    return {
        "id": resource.id,
        "teacher_id": resource.teacher_id,
        "teacher_name": teacher_name,
        "title": resource.title,
        "description": resource.description,
        "resource_type": resource.resource_type,
        "subject": resource.subject,
        "grade_level": resource.grade_level,
        "tags": _deserialize_tags(resource.tags),
        "is_public": resource.is_public,
        "file_key": resource.file_key,
        "external_url": resource.external_url,
        "download_count": resource.download_count,
        "avg_rating": resource.avg_rating,
        "rating_count": resource.rating_count,
        "curriculum_expectation": resource.curriculum_expectation,
        "linked_lesson_plan_id": resource.linked_lesson_plan_id,
        "created_at": resource.created_at,
        "updated_at": resource.updated_at,
    }


class ResourceLibraryService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Resources
    # ------------------------------------------------------------------

    def create_resource(self, teacher_id: int, data: TeacherResourceCreate) -> TeacherResource:
        resource = TeacherResource(
            teacher_id=teacher_id,
            title=data.title,
            description=data.description,
            resource_type=data.resource_type,
            subject=data.subject,
            grade_level=data.grade_level,
            tags=_serialize_tags(data.tags),
            is_public=data.is_public,
            external_url=data.external_url,
            curriculum_expectation=data.curriculum_expectation,
        )
        self.db.add(resource)
        self.db.commit()
        self.db.refresh(resource)
        logger.info("Created resource %d for teacher %d", resource.id, teacher_id)
        return resource

    def update_resource(
        self, resource_id: int, teacher_id: int, data: TeacherResourceUpdate
    ) -> TeacherResource:
        resource = self._get_owned_resource(resource_id, teacher_id)
        update_data = data.model_dump(exclude_unset=True)
        if "tags" in update_data:
            update_data["tags"] = _serialize_tags(update_data["tags"])
        for field, value in update_data.items():
            setattr(resource, field, value)
        self.db.commit()
        self.db.refresh(resource)
        return resource

    def delete_resource(self, resource_id: int, teacher_id: int, is_admin: bool = False) -> None:
        resource = self.db.query(TeacherResource).filter(
            TeacherResource.id == resource_id
        ).first()
        if not resource:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
        if not is_admin and resource.teacher_id != teacher_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your resource")

        # Delete stored file if one exists
        if resource.file_key:
            try:
                from app.services.storage_service import delete_file
                delete_file(resource.file_key)
            except Exception as e:
                logger.warning("Failed to delete file for resource %d: %s", resource_id, e)

        self.db.delete(resource)
        self.db.commit()

    def search_resources(
        self, params: ResourceSearchParams, viewer_id: Optional[int] = None
    ) -> Tuple[List[dict], int]:
        """Return paginated list of resources.

        Public resources are visible to everyone (authenticated).
        A teacher can additionally see their own private resources.
        """
        query = self.db.query(TeacherResource)

        # Visibility filter: public OR own resources
        from sqlalchemy import or_
        if viewer_id is not None:
            query = query.filter(
                or_(TeacherResource.is_public == True, TeacherResource.teacher_id == viewer_id)  # noqa: E712
            )
        else:
            query = query.filter(TeacherResource.is_public == True)  # noqa: E712

        if params.q:
            search = f"%{params.q}%"
            from sqlalchemy import or_
            query = query.filter(
                or_(
                    TeacherResource.title.ilike(search),
                    TeacherResource.description.ilike(search),
                )
            )
        if params.subject:
            query = query.filter(TeacherResource.subject.ilike(f"%{params.subject}%"))
        if params.grade_level:
            query = query.filter(TeacherResource.grade_level == params.grade_level)
        if params.resource_type:
            query = query.filter(TeacherResource.resource_type == params.resource_type)
        if params.tags:
            # Filter resources that contain at least one of the requested tags
            for tag in params.tags:
                query = query.filter(TeacherResource.tags.ilike(f"%{tag}%"))

        total = query.count()
        offset = (params.page - 1) * params.limit
        resources = (
            query
            .order_by(TeacherResource.created_at.desc())
            .offset(offset)
            .limit(params.limit)
            .all()
        )

        # Build response dicts with teacher names
        result = []
        for r in resources:
            teacher_name = None
            if r.teacher:
                teacher_name = r.teacher.full_name
            result.append(_resource_to_dict(r, teacher_name))

        import math
        pages = math.ceil(total / params.limit) if total > 0 else 1
        return result, total, pages

    def get_resource(
        self,
        resource_id: int,
        viewer_id: Optional[int] = None,
        increment_downloads: bool = False,
    ) -> dict:
        resource = self.db.query(TeacherResource).filter(
            TeacherResource.id == resource_id
        ).first()
        if not resource:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")

        # Access check
        if not resource.is_public and resource.teacher_id != viewer_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Resource not accessible")

        # Increment download count if viewer is not the owner
        if increment_downloads and viewer_id and viewer_id != resource.teacher_id:
            resource.download_count = (resource.download_count or 0) + 1
            self.db.commit()
            self.db.refresh(resource)

        teacher_name = resource.teacher.full_name if resource.teacher else None
        return _resource_to_dict(resource, teacher_name)

    def get_my_resources(self, teacher_id: int) -> List[dict]:
        resources = (
            self.db.query(TeacherResource)
            .filter(TeacherResource.teacher_id == teacher_id)
            .order_by(TeacherResource.created_at.desc())
            .all()
        )
        result = []
        for r in resources:
            teacher_name = r.teacher.full_name if r.teacher else None
            result.append(_resource_to_dict(r, teacher_name))
        return result

    def set_file_key(self, resource_id: int, teacher_id: int, file_key: str) -> TeacherResource:
        resource = self._get_owned_resource(resource_id, teacher_id)
        resource.file_key = file_key
        self.db.commit()
        self.db.refresh(resource)
        return resource

    # ------------------------------------------------------------------
    # Ratings
    # ------------------------------------------------------------------

    def rate_resource(
        self,
        resource_id: int,
        teacher_id: int,
        rating: int,
        comment: Optional[str],
    ) -> ResourceRating:
        resource = self.db.query(TeacherResource).filter(
            TeacherResource.id == resource_id
        ).first()
        if not resource:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
        if not resource.is_public and resource.teacher_id != teacher_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Resource not accessible")
        if resource.teacher_id == teacher_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot rate your own resource",
            )

        existing = self.db.query(ResourceRating).filter(
            ResourceRating.resource_id == resource_id,
            ResourceRating.teacher_id == teacher_id,
        ).first()

        if existing:
            # Update aggregate: subtract old, add new
            resource.rating_sum = (resource.rating_sum or 0) - existing.rating + rating
            existing.rating = rating
            existing.comment = comment
            rr = existing
        else:
            rr = ResourceRating(
                resource_id=resource_id,
                teacher_id=teacher_id,
                rating=rating,
                comment=comment,
            )
            self.db.add(rr)
            resource.rating_sum = (resource.rating_sum or 0) + rating
            resource.rating_count = (resource.rating_count or 0) + 1

        self.db.commit()
        self.db.refresh(rr)
        return rr

    # ------------------------------------------------------------------
    # Collections
    # ------------------------------------------------------------------

    def create_collection(self, teacher_id: int, name: str, description: Optional[str], resource_ids: Optional[List[int]]) -> ResourceCollection:
        collection = ResourceCollection(
            teacher_id=teacher_id,
            name=name,
            description=description,
            resource_ids=_serialize_resource_ids(resource_ids or []),
        )
        self.db.add(collection)
        self.db.commit()
        self.db.refresh(collection)
        return collection

    def add_to_collection(self, collection_id: int, resource_id: int, teacher_id: int) -> ResourceCollection:
        collection = self.db.query(ResourceCollection).filter(
            ResourceCollection.id == collection_id,
            ResourceCollection.teacher_id == teacher_id,
        ).first()
        if not collection:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")

        # Verify resource exists and is accessible
        resource = self.db.query(TeacherResource).filter(
            TeacherResource.id == resource_id
        ).first()
        if not resource:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
        if not resource.is_public and resource.teacher_id != teacher_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Resource not accessible")

        ids = _deserialize_resource_ids(collection.resource_ids)
        if resource_id not in ids:
            ids.append(resource_id)
            collection.resource_ids = _serialize_resource_ids(ids)
            self.db.commit()
            self.db.refresh(collection)
        return collection

    def get_collections(self, teacher_id: int) -> List[ResourceCollection]:
        return (
            self.db.query(ResourceCollection)
            .filter(ResourceCollection.teacher_id == teacher_id)
            .order_by(ResourceCollection.created_at.desc())
            .all()
        )

    def get_collection(self, collection_id: int, teacher_id: int) -> dict:
        collection = self.db.query(ResourceCollection).filter(
            ResourceCollection.id == collection_id,
            ResourceCollection.teacher_id == teacher_id,
        ).first()
        if not collection:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")

        ids = _deserialize_resource_ids(collection.resource_ids)
        resources_list = []
        if ids:
            rs = self.db.query(TeacherResource).filter(TeacherResource.id.in_(ids)).all()
            rs_map = {r.id: r for r in rs}
            for rid in ids:
                if rid in rs_map:
                    r = rs_map[rid]
                    resources_list.append(_resource_to_dict(r, r.teacher.full_name if r.teacher else None))

        return {
            "id": collection.id,
            "teacher_id": collection.teacher_id,
            "name": collection.name,
            "description": collection.description,
            "resource_ids": ids,
            "resources": resources_list,
            "created_at": collection.created_at,
            "updated_at": collection.updated_at,
        }

    # ------------------------------------------------------------------
    # Remix: create a stub lesson plan from a resource
    # ------------------------------------------------------------------

    def remix_into_lesson_plan(self, resource_id: int, teacher_id: int) -> LessonPlan:
        """Create a stub daily lesson plan from a resource's title and description."""
        resource = self.db.query(TeacherResource).filter(
            TeacherResource.id == resource_id
        ).first()
        if not resource:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
        if not resource.is_public and resource.teacher_id != teacher_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Resource not accessible")

        # Resolve the teacher record for this user
        teacher = self.db.query(Teacher).filter(Teacher.user_id == teacher_id).first()
        if not teacher:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Teacher profile not found",
            )

        plan = LessonPlan(
            teacher_id=teacher.id,
            plan_type=LessonPlanType.DAILY,
            title=f"Remixed: {resource.title}",
            grade_level=resource.grade_level,
            imported_from="resource_library",
            materials_resources=json.dumps([resource.title]),
        )
        if resource.description:
            plan.big_ideas = json.dumps([resource.description[:500]])
        if resource.curriculum_expectation:
            plan.curriculum_expectations = json.dumps([resource.curriculum_expectation])

        self.db.add(plan)
        self.db.flush()  # get plan.id

        # Link resource to plan
        resource.linked_lesson_plan_id = plan.id
        self.db.commit()
        self.db.refresh(plan)
        logger.info("Remixed resource %d into lesson plan %d", resource_id, plan.id)
        return plan

    # ------------------------------------------------------------------
    # Discovery helpers
    # ------------------------------------------------------------------

    def get_distinct_subjects(self) -> List[str]:
        rows = (
            self.db.query(TeacherResource.subject)
            .filter(TeacherResource.is_public == True, TeacherResource.subject.isnot(None))  # noqa: E712
            .distinct()
            .order_by(TeacherResource.subject)
            .all()
        )
        return [r[0] for r in rows if r[0]]

    def get_library_stats(self) -> dict:
        from sqlalchemy import func as sqlfunc
        total_resources = self.db.query(TeacherResource).count()
        public_resources = self.db.query(TeacherResource).filter(TeacherResource.is_public == True).count()  # noqa: E712
        total_downloads = self.db.query(sqlfunc.sum(TeacherResource.download_count)).scalar() or 0
        total_ratings = self.db.query(ResourceRating).count()

        avg_rating_result = self.db.query(
            sqlfunc.avg(
                sqlfunc.cast(TeacherResource.rating_sum, sqlfunc.Float())
                / sqlfunc.cast(TeacherResource.rating_count, sqlfunc.Float())
            )
        ).filter(TeacherResource.rating_count > 0).scalar()

        avg_rating = round(float(avg_rating_result), 2) if avg_rating_result else 0.0

        return {
            "total_resources": total_resources,
            "public_resources": public_resources,
            "total_downloads": total_downloads,
            "total_ratings": total_ratings,
            "avg_rating": avg_rating,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_owned_resource(self, resource_id: int, teacher_id: int) -> TeacherResource:
        resource = self.db.query(TeacherResource).filter(
            TeacherResource.id == resource_id,
            TeacherResource.teacher_id == teacher_id,
        ).first()
        if not resource:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found or not owned by you",
            )
        return resource
