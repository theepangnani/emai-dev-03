"""
Feature Flags API routes.

User-facing:
    GET  /api/feature-flags            — all flags evaluated for current user
    GET  /api/feature-flags/{key}      — single flag evaluation for current user

Admin CRUD (require ADMIN role):
    GET    /api/admin/feature-flags              — list all flags with full config
    POST   /api/admin/feature-flags              — create flag
    PUT    /api/admin/feature-flags/{key}        — update flag
    DELETE /api/admin/feature-flags/{key}        — delete flag

Admin overrides:
    GET    /api/admin/feature-flags/overrides        — list overrides (paginated)
    POST   /api/admin/feature-flags/overrides        — create override
    DELETE /api/admin/feature-flags/overrides/{id}   — remove override

Admin seed:
    POST   /api/admin/feature-flags/seed             — seed predefined flags (idempotent)

# NOTE FOR main.py:
#   After Base.metadata.create_all() call, add:
#       from app.api.routes.feature_flags import seed_default_flags
#       seed_default_flags(db)
#   Also include the routers:
#       from app.api.routes.feature_flags import router as feature_flags_router, admin_router as ff_admin_router
#       app.include_router(feature_flags_router)
#       app.include_router(ff_admin_router)
"""

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.database import get_db
from app.models.feature_flag import FeatureFlag, FlagScope, UserFeatureOverride
from app.models.user import User, UserRole
from app.services.feature_flags import (
    FeatureFlagService,
    get_feature_flag_service,
    invalidate_cache,
)

logger = logging.getLogger(__name__)

# ─── Routers ──────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/feature-flags", tags=["feature-flags"])
admin_router = APIRouter(prefix="/admin/feature-flags", tags=["admin-feature-flags"])

# ─── Schemas ──────────────────────────────────────────────────────────────────


class FeatureFlagCreate(BaseModel):
    key: str
    name: str
    description: Optional[str] = None
    scope: str = FlagScope.GLOBAL.value
    is_enabled: bool = False
    enabled_tiers: list[str] = []
    enabled_roles: list[str] = []
    enabled_user_ids: list[int] = []
    rollout_percentage: int = 100
    metadata_json: dict = {}


class FeatureFlagUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    scope: Optional[str] = None
    is_enabled: Optional[bool] = None
    enabled_tiers: Optional[list[str]] = None
    enabled_roles: Optional[list[str]] = None
    enabled_user_ids: Optional[list[int]] = None
    rollout_percentage: Optional[int] = None
    metadata_json: Optional[dict] = None


class FeatureFlagResponse(BaseModel):
    id: int
    key: str
    name: str
    description: Optional[str]
    scope: str
    is_enabled: bool
    enabled_tiers: list[str]
    enabled_roles: list[str]
    enabled_user_ids: list[int]
    rollout_percentage: int
    metadata_json: dict
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    created_by_user_id: Optional[int]

    model_config = {"from_attributes": True}


class OverrideCreate(BaseModel):
    user_id: int
    flag_key: str
    is_enabled: bool
    reason: Optional[str] = None
    expires_at: Optional[datetime] = None


class OverrideResponse(BaseModel):
    id: int
    user_id: int
    flag_key: str
    is_enabled: bool
    reason: Optional[str]
    expires_at: Optional[datetime]
    created_by_user_id: Optional[int]
    created_at: Optional[datetime]

    model_config = {"from_attributes": True}


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _flag_to_response(flag: FeatureFlag) -> FeatureFlagResponse:
    def _parse(val: str, default) -> list:
        try:
            return json.loads(val or "[]")
        except Exception:
            return default

    return FeatureFlagResponse(
        id=flag.id,
        key=flag.key,
        name=flag.name,
        description=flag.description,
        scope=flag.scope,
        is_enabled=flag.is_enabled,
        enabled_tiers=_parse(flag.enabled_tiers, []),
        enabled_roles=_parse(flag.enabled_roles, []),
        enabled_user_ids=_parse(flag.enabled_user_ids, []),
        rollout_percentage=flag.rollout_percentage,
        metadata_json=_parse(flag.metadata_json, {}),
        created_at=flag.created_at,
        updated_at=flag.updated_at,
        created_by_user_id=flag.created_by_user_id,
    )


# ─── User-facing endpoints ────────────────────────────────────────────────────


@router.get("", response_model=dict[str, bool])
def get_all_flags_for_user(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    svc: FeatureFlagService = Depends(get_feature_flag_service),
):
    """Return all feature flags evaluated for the current user."""
    return svc.get_all_flags_for_user(current_user, db)


@router.get("/{key}", response_model=dict)
def get_single_flag_for_user(
    key: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    svc: FeatureFlagService = Depends(get_feature_flag_service),
):
    """Return a single flag evaluation for the current user."""
    flag = svc.get_flag(key, db)
    if flag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Flag '{key}' not found")
    enabled = svc.is_enabled(key, current_user, db)
    return {"key": key, "enabled": enabled}


# ─── Admin CRUD ───────────────────────────────────────────────────────────────


@admin_router.get("/overrides", response_model=dict)
def list_overrides(
    user_id: Optional[int] = None,
    flag_key: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """List all user feature overrides, optionally filtered by user or flag."""
    query = db.query(UserFeatureOverride)
    if user_id is not None:
        query = query.filter(UserFeatureOverride.user_id == user_id)
    if flag_key:
        query = query.filter(UserFeatureOverride.flag_key == flag_key)
    total = query.count()
    items = query.order_by(UserFeatureOverride.created_at.desc()).offset(skip).limit(limit).all()
    return {
        "items": [OverrideResponse.model_validate(o) for o in items],
        "total": total,
    }


@admin_router.post("/overrides", response_model=OverrideResponse, status_code=status.HTTP_201_CREATED)
def create_override(
    data: OverrideCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Create or update a per-user feature override."""
    # Verify flag exists
    flag = db.query(FeatureFlag).filter(FeatureFlag.key == data.flag_key).first()
    if not flag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature flag '{data.flag_key}' not found",
        )

    # Upsert
    existing = (
        db.query(UserFeatureOverride)
        .filter(
            UserFeatureOverride.user_id == data.user_id,
            UserFeatureOverride.flag_key == data.flag_key,
        )
        .first()
    )
    if existing:
        existing.is_enabled = data.is_enabled
        existing.reason = data.reason
        existing.expires_at = data.expires_at
        existing.created_by_user_id = current_user.id
        override = existing
    else:
        override = UserFeatureOverride(
            user_id=data.user_id,
            flag_key=data.flag_key,
            is_enabled=data.is_enabled,
            reason=data.reason,
            expires_at=data.expires_at,
            created_by_user_id=current_user.id,
        )
        db.add(override)

    db.commit()
    db.refresh(override)
    invalidate_cache()
    logger.info(
        "Admin %s %s override: user=%s flag=%s enabled=%s",
        current_user.id,
        "updated" if existing else "created",
        data.user_id,
        data.flag_key,
        data.is_enabled,
    )
    return OverrideResponse.model_validate(override)


@admin_router.delete("/overrides/{override_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_override(
    override_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Remove a user feature override."""
    override = db.query(UserFeatureOverride).filter(UserFeatureOverride.id == override_id).first()
    if not override:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Override not found")
    db.delete(override)
    db.commit()
    invalidate_cache()


@admin_router.post("/seed", status_code=status.HTTP_200_OK)
def seed_flags(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Seed predefined feature flags. Idempotent — safe to call multiple times."""
    seed_default_flags(db)
    invalidate_cache()
    return {"message": "Default flags seeded"}


@admin_router.get("", response_model=list[FeatureFlagResponse])
def list_flags(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """List all feature flags with full configuration."""
    flags = db.query(FeatureFlag).order_by(FeatureFlag.key).all()
    return [_flag_to_response(f) for f in flags]


@admin_router.post("", response_model=FeatureFlagResponse, status_code=status.HTTP_201_CREATED)
def create_flag(
    data: FeatureFlagCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Create a new feature flag."""
    if db.query(FeatureFlag).filter(FeatureFlag.key == data.key).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Flag with key '{data.key}' already exists",
        )
    if data.scope not in [s.value for s in FlagScope]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid scope '{data.scope}'. Must be one of: {[s.value for s in FlagScope]}",
        )
    flag = FeatureFlag(
        key=data.key,
        name=data.name,
        description=data.description,
        scope=data.scope,
        is_enabled=data.is_enabled,
        enabled_tiers=json.dumps(data.enabled_tiers),
        enabled_roles=json.dumps(data.enabled_roles),
        enabled_user_ids=json.dumps(data.enabled_user_ids),
        rollout_percentage=data.rollout_percentage,
        metadata_json=json.dumps(data.metadata_json),
        created_by_user_id=current_user.id,
    )
    db.add(flag)
    db.commit()
    db.refresh(flag)
    invalidate_cache()
    logger.info("Admin %s created feature flag '%s'", current_user.id, data.key)
    return _flag_to_response(flag)


@admin_router.put("/{key}", response_model=FeatureFlagResponse)
def update_flag(
    key: str,
    data: FeatureFlagUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Update a feature flag (toggle, scope, tiers, rollout %, etc.)."""
    flag = db.query(FeatureFlag).filter(FeatureFlag.key == key).first()
    if not flag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Flag '{key}' not found")

    if data.name is not None:
        flag.name = data.name
    if data.description is not None:
        flag.description = data.description
    if data.scope is not None:
        if data.scope not in [s.value for s in FlagScope]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid scope '{data.scope}'",
            )
        flag.scope = data.scope
    if data.is_enabled is not None:
        flag.is_enabled = data.is_enabled
    if data.enabled_tiers is not None:
        flag.enabled_tiers = json.dumps(data.enabled_tiers)
    if data.enabled_roles is not None:
        flag.enabled_roles = json.dumps(data.enabled_roles)
    if data.enabled_user_ids is not None:
        flag.enabled_user_ids = json.dumps(data.enabled_user_ids)
    if data.rollout_percentage is not None:
        if not (0 <= data.rollout_percentage <= 100):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="rollout_percentage must be between 0 and 100",
            )
        flag.rollout_percentage = data.rollout_percentage
    if data.metadata_json is not None:
        flag.metadata_json = json.dumps(data.metadata_json)

    db.commit()
    db.refresh(flag)
    invalidate_cache()
    logger.info("Admin %s updated feature flag '%s'", current_user.id, key)
    return _flag_to_response(flag)


@admin_router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_flag(
    key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Delete a feature flag and all its overrides."""
    flag = db.query(FeatureFlag).filter(FeatureFlag.key == key).first()
    if not flag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Flag '{key}' not found")
    # Remove overrides first
    db.query(UserFeatureOverride).filter(UserFeatureOverride.flag_key == key).delete(
        synchronize_session=False
    )
    db.delete(flag)
    db.commit()
    invalidate_cache()
    logger.info("Admin %s deleted feature flag '%s'", current_user.id, key)


# ─── Seed helper (called from main.py startup) ────────────────────────────────


def seed_default_flags(db: Session) -> None:
    """
    Seed the eight predefined feature flags if they do not already exist.
    This function is idempotent — safe to call on every application startup.

    Call from main.py after Base.metadata.create_all(bind=engine):
        from app.api.routes.feature_flags import seed_default_flags
        seed_default_flags(db)
    """
    defaults = [
        {
            "key": "ai_email_agent",
            "name": "AI Email Agent",
            "description": "Enables the Phase 5 AI Email Agent feature for automated email processing.",
            "scope": FlagScope.GLOBAL.value,
            "is_enabled": True,
            "enabled_roles": [],
            "enabled_tiers": [],
        },
        {
            "key": "tutor_marketplace",
            "name": "Tutor Marketplace",
            "description": "Enables the tutor marketplace where students/parents can discover and hire tutors.",
            "scope": FlagScope.GLOBAL.value,
            "is_enabled": True,
            "enabled_roles": [],
            "enabled_tiers": [],
        },
        {
            "key": "lesson_planner",
            "name": "Lesson Planner",
            "description": "Enables the AI-powered lesson planner available to teachers and admins.",
            "scope": FlagScope.ROLE.value,
            "is_enabled": False,
            "enabled_roles": ["teacher", "admin"],
            "enabled_tiers": [],
        },
        {
            "key": "ai_personalization",
            "name": "AI Personalization",
            "description": "Enables adaptive learning, mastery tracking, and learning-style detection.",
            "scope": FlagScope.GLOBAL.value,
            "is_enabled": True,
            "enabled_roles": [],
            "enabled_tiers": [],
        },
        {
            "key": "brightspace_lms",
            "name": "Brightspace LMS",
            "description": "Enables Brightspace LMS OAuth2 integration (premium tier only).",
            "scope": FlagScope.TIER.value,
            "is_enabled": False,
            "enabled_roles": [],
            "enabled_tiers": ["premium"],
        },
        {
            "key": "stripe_billing",
            "name": "Stripe Billing",
            "description": "Enables Stripe payment and subscription management.",
            "scope": FlagScope.GLOBAL.value,
            "is_enabled": True,
            "enabled_roles": [],
            "enabled_tiers": [],
        },
        {
            "key": "mcp_tools",
            "name": "MCP Tools",
            "description": "Enables MCP (Model Context Protocol) tools for teachers and admins.",
            "scope": FlagScope.ROLE.value,
            "is_enabled": False,
            "enabled_roles": ["teacher", "admin"],
            "enabled_tiers": [],
        },
        {
            "key": "beta_features",
            "name": "Beta Features",
            "description": "Grants access to early-access beta features via per-user opt-in.",
            "scope": FlagScope.BETA.value,
            "is_enabled": False,
            "enabled_roles": [],
            "enabled_tiers": [],
        },
    ]

    seeded = 0
    for entry in defaults:
        existing = db.query(FeatureFlag).filter(FeatureFlag.key == entry["key"]).first()
        if not existing:
            flag = FeatureFlag(
                key=entry["key"],
                name=entry["name"],
                description=entry.get("description"),
                scope=entry["scope"],
                is_enabled=entry["is_enabled"],
                enabled_tiers=json.dumps(entry.get("enabled_tiers", [])),
                enabled_roles=json.dumps(entry.get("enabled_roles", [])),
                enabled_user_ids=json.dumps([]),
                rollout_percentage=100,
                metadata_json=json.dumps({}),
            )
            db.add(flag)
            seeded += 1

    if seeded:
        try:
            db.commit()
            logger.info("Feature flags: seeded %d default flag(s)", seeded)
        except Exception as exc:
            db.rollback()
            logger.warning("Failed to seed feature flags: %s", exc)
    else:
        logger.debug("Feature flags: all defaults already present")
