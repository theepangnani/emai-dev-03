"""Link request routes for parent-student approval workflows.

Stub router created as part of Phase 0 foundation.
Stream A will implement the full CRUD + approve/reject endpoints.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/link-requests", tags=["link-requests"])
