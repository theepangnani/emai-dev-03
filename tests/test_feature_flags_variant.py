"""Tests for feature flag A/B variant support (#3601, CB-DEMO-001 F2).

Covers:
- `variant` column exists on feature_flags after startup.
- `seed_features()` seeds `demo_landing_v1_1` with variant='off' idempotently.
- `/api/features` response exposes `_variants` map for authenticated users.
- Admin `PATCH /api/admin/features/{key}` accepts variant updates and
  validates the variant value.
"""

import pytest
from sqlalchemy import inspect as sa_inspect

from conftest import PASSWORD, _auth


@pytest.fixture()
def admin_user(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    email = "variant_admin@test.com"
    admin = db_session.query(User).filter(User.email == email).first()
    if admin is None:
        admin = User(
            email=email,
            full_name="Variant Admin",
            role=UserRole.ADMIN,
            hashed_password=get_password_hash(PASSWORD),
        )
        db_session.add(admin)
        db_session.commit()
        db_session.refresh(admin)
    return admin


def test_feature_flags_table_has_variant_column(db_session):
    """Model + create_all should produce a `variant` column on feature_flags."""
    from app.db.database import engine

    inspector = sa_inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("feature_flags")}
    assert "variant" in cols, f"Expected 'variant' column on feature_flags, got: {cols}"


def test_seed_features_idempotent_for_demo_landing(db_session):
    """seed_features() must add demo_landing_v1_1 with variant='off' and be idempotent."""
    from app.models.feature_flag import FeatureFlag
    from app.services.feature_seed_service import seed_features

    # Seed (may be first run or a no-op if already seeded)
    seed_features(db_session)
    flag = db_session.query(FeatureFlag).filter(FeatureFlag.key == "demo_landing_v1_1").first()
    assert flag is not None, "demo_landing_v1_1 should be seeded"
    assert flag.enabled is False
    assert flag.variant == "off"

    # Running again must NOT duplicate or change the existing flag.
    before_count = db_session.query(FeatureFlag).filter(FeatureFlag.key == "demo_landing_v1_1").count()
    seed_features(db_session)
    after_count = db_session.query(FeatureFlag).filter(FeatureFlag.key == "demo_landing_v1_1").count()
    assert before_count == after_count == 1


def test_public_features_includes_variants_for_authenticated(client, db_session):
    """Authenticated `/api/features` must include a `_variants` map keyed by flag."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.feature_flag import FeatureFlag
    from app.services.feature_seed_service import seed_features

    # Ensure demo_landing_v1_1 exists
    seed_features(db_session)

    email = "variant_parent@test.com"
    if not db_session.query(User).filter(User.email == email).first():
        db_session.add(User(
            email=email,
            full_name="Parent Variant",
            role=UserRole.PARENT,
            hashed_password=get_password_hash(PASSWORD),
        ))
        db_session.commit()

    headers = _auth(client, email)
    resp = client.get("/api/features", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "_variants" in data
    assert isinstance(data["_variants"], dict)
    # demo_landing_v1_1 should be present with variant 'off'
    assert data["_variants"].get("demo_landing_v1_1") == "off"

    # Boolean shape preserved for existing consumers
    assert data.get("demo_landing_v1_1") is False
    _ = db_session.query(FeatureFlag).all()  # ensure query path works


def test_public_features_unauthenticated_exposes_demo_landing_variant(client, db_session):
    """`/api/features` without auth must expose demo_landing_v1_1 variant
    so the public landing page can gate on it (#3715). Other DB-backed
    flags remain admin-only.
    """
    from app.services.feature_seed_service import seed_features
    from app.models.feature_flag import FeatureFlag

    # Ensure the public demo flag is seeded.
    seed_features(db_session)

    resp = client.get("/api/features")
    assert resp.status_code == 200
    data = resp.json()

    # Config-based flags still present.
    assert "google_classroom" in data
    assert "waitlist_enabled" in data

    # _PUBLIC_DB_FLAGS — demo_landing_v1_1 MUST appear for unauthenticated
    # callers so useVariantBucket on the landing page works.
    assert "demo_landing_v1_1" in data
    assert "_variants" in data
    assert "demo_landing_v1_1" in data["_variants"]
    assert data["_variants"]["demo_landing_v1_1"] in {"off", "on_50", "on_for_all"}

    # Non-public DB-backed flags must NOT leak to unauthenticated callers.
    # Seed a non-public flag and assert it's absent.
    leakable = db_session.query(FeatureFlag).filter(
        FeatureFlag.key == "school_board_connectivity"
    ).first()
    if leakable is None:
        leakable = FeatureFlag(
            key="school_board_connectivity",
            name="School Board Connectivity",
            description="test",
            enabled=False,
        )
        db_session.add(leakable)
        db_session.commit()
    # Re-fetch with the flag now seeded.
    resp2 = client.get("/api/features")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert "school_board_connectivity" not in data2
    assert "school_board_connectivity" not in data2.get("_variants", {})


def test_admin_update_variant_valid(client, db_session, admin_user):
    """Admin can set variant to a valid value."""
    from app.services.feature_seed_service import seed_features
    from app.models.feature_flag import FeatureFlag

    seed_features(db_session)
    headers = _auth(client, admin_user.email)

    resp = client.patch(
        "/api/admin/features/demo_landing_v1_1",
        headers=headers,
        json={"variant": "on_50"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["variant"] == "on_50"

    # Persisted
    db_session.expire_all()
    flag = db_session.query(FeatureFlag).filter(FeatureFlag.key == "demo_landing_v1_1").first()
    assert flag.variant == "on_50"

    # Reset back to 'off' to not leak state to other tests
    client.patch(
        "/api/admin/features/demo_landing_v1_1",
        headers=headers,
        json={"variant": "off"},
    )


def test_admin_update_config_based_flag_rejects_variant(client, db_session, admin_user):
    """Config-based flags (e.g. google_classroom) must reject variant updates (#3629)."""
    headers = _auth(client, admin_user.email)

    resp = client.patch(
        "/api/admin/features/google_classroom",
        headers=headers,
        json={"variant": "on_50"},
    )
    assert resp.status_code == 400, resp.text
    detail = resp.json()["detail"]
    assert "variant" in detail.lower()
    assert "google_classroom" in detail or "config-based" in detail.lower()


def test_admin_update_variant_rejects_invalid_value(client, db_session, admin_user):
    """Invalid variant values must return 400."""
    from app.services.feature_seed_service import seed_features

    seed_features(db_session)
    headers = _auth(client, admin_user.email)

    resp = client.patch(
        "/api/admin/features/demo_landing_v1_1",
        headers=headers,
        json={"variant": "bogus"},
    )
    assert resp.status_code == 400
    assert "variant" in resp.json()["detail"].lower()


def test_admin_update_requires_enabled_or_variant(client, db_session, admin_user):
    """PATCH with an empty body must return 400."""
    from app.services.feature_seed_service import seed_features

    seed_features(db_session)
    headers = _auth(client, admin_user.email)

    resp = client.patch(
        "/api/admin/features/demo_landing_v1_1",
        headers=headers,
        json={},
    )
    assert resp.status_code == 400


def test_admin_update_enabled_still_works_backcompat(client, db_session, admin_user):
    """Existing boolean-only toggle path must still succeed (back-compat)."""
    from app.services.feature_seed_service import seed_features
    from app.models.feature_flag import FeatureFlag

    seed_features(db_session)
    headers = _auth(client, admin_user.email)

    resp = client.patch(
        "/api/admin/features/demo_landing_v1_1",
        headers=headers,
        json={"enabled": True},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["enabled"] is True
    assert "variant" in body  # variant now part of response payload

    # Reset
    client.patch(
        "/api/admin/features/demo_landing_v1_1",
        headers=headers,
        json={"enabled": False},
    )
    db_session.expire_all()
    flag = db_session.query(FeatureFlag).filter(FeatureFlag.key == "demo_landing_v1_1").first()
    assert flag.enabled is False


def test_admin_get_features_exposes_variant(client, db_session, admin_user):
    """GET /api/admin/features must include `variant` on each DB-backed flag."""
    from app.services.feature_seed_service import seed_features

    seed_features(db_session)
    headers = _auth(client, admin_user.email)

    resp = client.get("/api/admin/features", headers=headers)
    assert resp.status_code == 200
    items = resp.json()
    demo = next((x for x in items if x["key"] == "demo_landing_v1_1"), None)
    assert demo is not None
    assert demo["variant"] == "off"


# -----------------------------------------------------------------------------
# CB-LAND-001 S2 (#3802) — landing_v2 flag
# -----------------------------------------------------------------------------


def test_seed_features_seeds_landing_v2(db_session):
    """seed_features() must add `landing_v2` with variant='off' idempotently."""
    from app.models.feature_flag import FeatureFlag
    from app.services.feature_seed_service import seed_features

    seed_features(db_session)
    flag = db_session.query(FeatureFlag).filter(FeatureFlag.key == "landing_v2").first()
    assert flag is not None, "landing_v2 should be seeded"
    assert flag.enabled is False
    assert flag.variant == "off"

    # Idempotent on re-seed
    seed_features(db_session)
    count = db_session.query(FeatureFlag).filter(FeatureFlag.key == "landing_v2").count()
    assert count == 1


def test_public_features_exposes_landing_v2_variant_unauthenticated(client, db_session):
    """Unauthenticated callers MUST see `landing_v2` variant (kill-switch lives
    on the anonymous landing page, so the flag must be public-readable).
    """
    from app.services.feature_seed_service import seed_features

    seed_features(db_session)

    resp = client.get("/api/features")
    assert resp.status_code == 200
    data = resp.json()
    assert "landing_v2" in data
    assert "landing_v2" in data.get("_variants", {})
    assert data["_variants"]["landing_v2"] in {
        "off", "on_5", "on_25", "on_50", "on_100", "on_for_all",
    }


@pytest.mark.parametrize("variant", ["on_5", "on_25", "on_50", "on_100"])
def test_admin_accepts_new_percentage_variants_for_landing_v2(
    client, db_session, admin_user, variant
):
    """PATCH /api/admin/features/landing_v2 must accept the CB-LAND-001
    percentage-ramp variants (on_5 / on_25 / on_50 / on_100).
    """
    from app.services.feature_seed_service import seed_features
    from app.models.feature_flag import FeatureFlag

    seed_features(db_session)
    headers = _auth(client, admin_user.email)

    resp = client.patch(
        "/api/admin/features/landing_v2",
        headers=headers,
        json={"variant": variant},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["variant"] == variant

    db_session.expire_all()
    flag = db_session.query(FeatureFlag).filter(FeatureFlag.key == "landing_v2").first()
    assert flag.variant == variant

    # Reset to 'off' to avoid leaking state into sibling tests
    client.patch(
        "/api/admin/features/landing_v2",
        headers=headers,
        json={"variant": "off"},
    )
