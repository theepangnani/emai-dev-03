"""Resource Library API routes.

Routes:
  GET    /api/resources/               — search/browse public resources
  GET    /api/resources/mine           — teacher: own resources
  GET    /api/resources/subjects       — list distinct subjects (for filter UI)
  GET    /api/resources/stats          — admin: library stats
  GET    /api/resources/collections/   — teacher: list collections
  POST   /api/resources/collections/   — teacher: create collection
  POST   /api/resources/collections/{id}/add  — teacher: add resource to collection
  GET    /api/resources/collections/{id}      — teacher: get collection with resources
  POST   /api/resources/               — teacher: create resource
  GET    /api/resources/{id}           — get resource detail
  PATCH  /api/resources/{id}           — teacher: update own resource
  DELETE /api/resources/{id}           — teacher/admin: delete resource
  POST   /api/resources/{id}/rate      — teacher: rate resource
  POST   /api/resources/{id}/remix     — teacher: remix into lesson plan
  POST   /api/resources/{id}/upload    — teacher: upload file to resource
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.api.deps import get_current_user, require_role
from app.models.user import User, UserRole
from app.schemas.resource_library import (
    TeacherResourceCreate,
    TeacherResourceResponse,
    TeacherResourceUpdate,
    ResourceRatingCreate,
    ResourceRatingResponse,
    ResourceCollectionCreate,
    ResourceCollectionResponse,
    ResourceSearchParams,
    PaginatedResourceResponse,
)
from app.services.resource_library import ResourceLibraryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resources", tags=["resource-library"])

# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------


def _service(db: Session = Depends(get_db)) -> ResourceLibraryService:
    return ResourceLibraryService(db)


def _teacher_or_admin(current_user: User = Depends(get_current_user)) -> User:
    if not (current_user.has_role(UserRole.TEACHER) or current_user.has_role(UserRole.ADMIN)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers and admins can access this endpoint",
        )
    return current_user


# ---------------------------------------------------------------------------
# Static / list endpoints (must come before /{id} to avoid conflicts)
# ---------------------------------------------------------------------------


@router.get("/subjects", response_model=List[str], summary="List distinct subjects")
def list_subjects(
    svc: ResourceLibraryService = Depends(_service),
    _current_user: User = Depends(get_current_user),
):
    """Return all distinct subject values from public resources (for filter UI)."""
    return svc.get_distinct_subjects()


@router.get("/stats", summary="Admin: resource library statistics")
def library_stats(
    svc: ResourceLibraryService = Depends(_service),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Return aggregate library stats (admin only)."""
    return svc.get_library_stats()


@router.get("/mine", response_model=List[TeacherResourceResponse], summary="My resources")
def my_resources(
    svc: ResourceLibraryService = Depends(_service),
    current_user: User = Depends(_teacher_or_admin),
):
    """Return all resources created by the current teacher."""
    return svc.get_my_resources(current_user.id)


@router.get("/collections/", response_model=List[ResourceCollectionResponse], summary="List collections")
def list_collections(
    svc: ResourceLibraryService = Depends(_service),
    current_user: User = Depends(_teacher_or_admin),
):
    """Return all personal resource collections for the current teacher."""
    collections = svc.get_collections(current_user.id)
    result = []
    from app.services.resource_library import _deserialize_resource_ids
    for c in collections:
        result.append({
            "id": c.id,
            "teacher_id": c.teacher_id,
            "name": c.name,
            "description": c.description,
            "resource_ids": _deserialize_resource_ids(c.resource_ids),
            "resources": None,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
        })
    return result


@router.post(
    "/collections/",
    response_model=ResourceCollectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create collection",
)
def create_collection(
    body: ResourceCollectionCreate,
    svc: ResourceLibraryService = Depends(_service),
    current_user: User = Depends(_teacher_or_admin),
):
    """Create a new personal resource collection."""
    c = svc.create_collection(
        teacher_id=current_user.id,
        name=body.name,
        description=body.description,
        resource_ids=body.resource_ids,
    )
    from app.services.resource_library import _deserialize_resource_ids
    return {
        "id": c.id,
        "teacher_id": c.teacher_id,
        "name": c.name,
        "description": c.description,
        "resource_ids": _deserialize_resource_ids(c.resource_ids),
        "resources": None,
        "created_at": c.created_at,
        "updated_at": c.updated_at,
    }


@router.post(
    "/collections/{collection_id}/add",
    response_model=ResourceCollectionResponse,
    summary="Add resource to collection",
)
def add_to_collection(
    collection_id: int,
    resource_id: int = Query(..., description="ID of the resource to add"),
    svc: ResourceLibraryService = Depends(_service),
    current_user: User = Depends(_teacher_or_admin),
):
    """Add a resource to a personal collection."""
    c = svc.add_to_collection(collection_id, resource_id, current_user.id)
    from app.services.resource_library import _deserialize_resource_ids
    return {
        "id": c.id,
        "teacher_id": c.teacher_id,
        "name": c.name,
        "description": c.description,
        "resource_ids": _deserialize_resource_ids(c.resource_ids),
        "resources": None,
        "created_at": c.created_at,
        "updated_at": c.updated_at,
    }


@router.get(
    "/collections/{collection_id}",
    response_model=ResourceCollectionResponse,
    summary="Get collection with resources",
)
def get_collection(
    collection_id: int,
    svc: ResourceLibraryService = Depends(_service),
    current_user: User = Depends(_teacher_or_admin),
):
    """Return a specific collection with its full resource details."""
    return svc.get_collection(collection_id, current_user.id)


# ---------------------------------------------------------------------------
# Browse / search public resources
# ---------------------------------------------------------------------------


@router.get("/", response_model=PaginatedResourceResponse, summary="Search resources")
def search_resources(
    q: Optional[str] = Query(None, description="Full-text search"),
    subject: Optional[str] = Query(None),
    grade_level: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    svc: ResourceLibraryService = Depends(_service),
    current_user: User = Depends(get_current_user),
):
    """Browse and search public resources. Teachers also see their own private resources."""
    from app.models.resource_library import ResourceType as RT
    rt = None
    if resource_type:
        try:
            rt = RT(resource_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid resource_type: {resource_type}")

    tags_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None

    params = ResourceSearchParams(
        q=q,
        subject=subject,
        grade_level=grade_level,
        resource_type=rt,
        tags=tags_list,
        page=page,
        limit=limit,
    )
    items, total, pages = svc.search_resources(params, viewer_id=current_user.id)
    return {"items": items, "total": total, "page": page, "limit": limit, "pages": pages}


# ---------------------------------------------------------------------------
# Create resource
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=TeacherResourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create resource",
)
def create_resource(
    body: TeacherResourceCreate,
    svc: ResourceLibraryService = Depends(_service),
    current_user: User = Depends(_teacher_or_admin),
):
    """Create a new teaching resource."""
    resource = svc.create_resource(current_user.id, body)
    return svc.get_resource(resource.id, viewer_id=current_user.id)


# ---------------------------------------------------------------------------
# Resource detail / edit / delete
# ---------------------------------------------------------------------------


@router.get("/{resource_id}", response_model=TeacherResourceResponse, summary="Get resource")
def get_resource(
    resource_id: int,
    svc: ResourceLibraryService = Depends(_service),
    current_user: User = Depends(get_current_user),
):
    """Get a single resource. Increments download_count if viewer is not the owner."""
    return svc.get_resource(resource_id, viewer_id=current_user.id, increment_downloads=True)


@router.patch("/{resource_id}", response_model=TeacherResourceResponse, summary="Update resource")
def update_resource(
    resource_id: int,
    body: TeacherResourceUpdate,
    svc: ResourceLibraryService = Depends(_service),
    current_user: User = Depends(_teacher_or_admin),
):
    """Update an owned resource."""
    resource = svc.update_resource(resource_id, current_user.id, body)
    return svc.get_resource(resource.id, viewer_id=current_user.id)


@router.delete("/{resource_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete resource")
def delete_resource(
    resource_id: int,
    svc: ResourceLibraryService = Depends(_service),
    current_user: User = Depends(_teacher_or_admin),
):
    """Delete a resource (owner or admin)."""
    is_admin = current_user.has_role(UserRole.ADMIN)
    svc.delete_resource(resource_id, current_user.id, is_admin=is_admin)


# ---------------------------------------------------------------------------
# Upload file to resource
# ---------------------------------------------------------------------------


@router.post("/{resource_id}/upload", response_model=TeacherResourceResponse, summary="Upload file")
async def upload_file(
    resource_id: int,
    file: UploadFile = File(...),
    svc: ResourceLibraryService = Depends(_service),
    current_user: User = Depends(_teacher_or_admin),
):
    """Upload a file and attach it to an existing resource."""
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:  # 50 MB limit
        raise HTTPException(status_code=413, detail="File too large (max 50 MB)")

    from app.services.storage_service import save_file
    file_key = save_file(content, file.filename or "upload")
    svc.set_file_key(resource_id, current_user.id, file_key)
    return svc.get_resource(resource_id, viewer_id=current_user.id)


# ---------------------------------------------------------------------------
# Rate resource
# ---------------------------------------------------------------------------


@router.post(
    "/{resource_id}/rate",
    response_model=ResourceRatingResponse,
    summary="Rate resource",
)
def rate_resource(
    resource_id: int,
    body: ResourceRatingCreate,
    svc: ResourceLibraryService = Depends(_service),
    current_user: User = Depends(_teacher_or_admin),
):
    """Rate a resource (1-5 stars). Upserts if already rated."""
    rr = svc.rate_resource(resource_id, current_user.id, body.rating, body.comment)
    teacher_name = current_user.full_name
    return {
        "id": rr.id,
        "resource_id": rr.resource_id,
        "teacher_id": rr.teacher_id,
        "teacher_name": teacher_name,
        "rating": rr.rating,
        "comment": rr.comment,
        "created_at": rr.created_at,
    }


# ---------------------------------------------------------------------------
# Remix resource into a lesson plan
# ---------------------------------------------------------------------------


@router.post(
    "/{resource_id}/remix",
    summary="Remix into lesson plan",
)
def remix_resource(
    resource_id: int,
    svc: ResourceLibraryService = Depends(_service),
    current_user: User = Depends(_teacher_or_admin),
):
    """Create a stub lesson plan from the resource content."""
    plan = svc.remix_into_lesson_plan(resource_id, current_user.id)
    return {
        "lesson_plan_id": plan.id,
        "title": plan.title,
        "plan_type": plan.plan_type,
        "message": "Lesson plan created. Edit it in the Lesson Planner.",
    }
