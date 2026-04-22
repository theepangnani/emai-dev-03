"""Regression tests for /api/features endpoint.

The endpoint must work without authentication (regression for #3239
login loop fix) and return expected config-based flags.
"""

import pytest

from conftest import PASSWORD, _auth


def _register(client, email, role="parent", full_name="Test User"):
    return client.post("/api/auth/register", json={
        "email": email, "password": PASSWORD, "full_name": full_name, "role": role,
    })


def test_features_unauthenticated(client):
    """Regression: /api/features must work without auth (fixes #3239)."""
    response = client.get("/api/features")
    assert response.status_code == 200
    data = response.json()
    assert "waitlist_enabled" in data
    assert "google_classroom" in data


def test_features_authenticated(client):
    """Authenticated users should get feature flags including DB-backed ones."""
    email = "features-auth@example.com"
    reg = _register(client, email)
    assert reg.status_code == 200, reg.text
    headers = _auth(client, email)

    response = client.get("/api/features", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "waitlist_enabled" in data
    assert "google_classroom" in data


# ---------------------------------------------------------------------------
# Kill-switch defense-in-depth (#3930, #3932 Stream B)
# ---------------------------------------------------------------------------
#
# When FeatureFlag.enabled is False, the /api/features response MUST coerce
# _variants[key] to "off" regardless of the stored `variant` column. This is
# defense-in-depth for non-frontend consumers (mobile, external API); the
# frontend `useVariantBucket` hook has its own guard (Stream A). The stored
# DB variant value MUST be preserved so flipping `enabled` back on restores
# the admin-configured rollout percentage.


@pytest.fixture()
def killswitch_flag(db_session):
    """Provide an isolated FeatureFlag row for kill-switch assertions."""
    from app.models.feature_flag import FeatureFlag

    key = "killswitch_test_flag_3932"
    flag = db_session.query(FeatureFlag).filter(FeatureFlag.key == key).first()
    if flag is None:
        flag = FeatureFlag(
            key=key,
            name="Killswitch Test Flag",
            description="Scratch flag for #3932 coverage.",
            enabled=False,
            variant="off",
        )
        db_session.add(flag)
        db_session.commit()
    yield flag
    # Cleanup so state does not leak into sibling tests
    db_session.delete(flag)
    db_session.commit()


def _fetch_variants_for_admin(client, db_session, key):
    """Authenticate as an admin and return `_variants[key]` from /api/features.

    Admin auth is required because arbitrary (non-_PUBLIC_DB_FLAGS) keys are
    only surfaced to authenticated callers.
    """
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    email = "killswitch_admin_3932@test.com"
    if not db_session.query(User).filter(User.email == email).first():
        db_session.add(User(
            email=email,
            full_name="Killswitch Admin",
            role=UserRole.ADMIN,
            hashed_password=get_password_hash(PASSWORD),
        ))
        db_session.commit()

    headers = _auth(client, email)
    resp = client.get("/api/features", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "_variants" in data
    return data["_variants"].get(key), data.get(key)


def test_variants_baseline_enabled_true_variant_on_for_all(
    client, db_session, killswitch_flag
):
    """enabled=True, variant='on_for_all' -> _variants[key] == 'on_for_all'."""
    killswitch_flag.enabled = True
    killswitch_flag.variant = "on_for_all"
    db_session.commit()

    variant, enabled = _fetch_variants_for_admin(
        client, db_session, killswitch_flag.key
    )
    assert variant == "on_for_all"
    assert enabled is True


def test_variants_coerced_to_off_when_enabled_false(
    client, db_session, killswitch_flag
):
    """THE FIX: enabled=False, variant='on_for_all' -> _variants[key] == 'off'.

    The stored `variant` column must be preserved ('on_for_all'); only the
    response payload is coerced.
    """
    from app.models.feature_flag import FeatureFlag

    killswitch_flag.enabled = False
    killswitch_flag.variant = "on_for_all"
    db_session.commit()

    variant, enabled = _fetch_variants_for_admin(
        client, db_session, killswitch_flag.key
    )
    assert variant == "off", (
        "Kill-switch defense-in-depth: _variants must be coerced to 'off' "
        "when enabled=False (#3930, #3932)."
    )
    assert enabled is False

    # Stored DB variant MUST be preserved so re-enabling the flag restores
    # the admin-configured rollout percentage.
    db_session.expire_all()
    persisted = (
        db_session.query(FeatureFlag)
        .filter(FeatureFlag.key == killswitch_flag.key)
        .first()
    )
    assert persisted.variant == "on_for_all", (
        "DB `variant` column must not be overwritten — only response is coerced."
    )


def test_variants_off_when_enabled_false_and_variant_off(
    client, db_session, killswitch_flag
):
    """enabled=False, variant='off' -> _variants[key] == 'off' (no regression)."""
    killswitch_flag.enabled = False
    killswitch_flag.variant = "off"
    db_session.commit()

    variant, enabled = _fetch_variants_for_admin(
        client, db_session, killswitch_flag.key
    )
    assert variant == "off"
    assert enabled is False


def test_variants_off_when_enabled_true_and_variant_off(
    client, db_session, killswitch_flag
):
    """enabled=True, variant='off' -> _variants[key] == 'off' (baseline)."""
    killswitch_flag.enabled = True
    killswitch_flag.variant = "off"
    db_session.commit()

    variant, enabled = _fetch_variants_for_admin(
        client, db_session, killswitch_flag.key
    )
    assert variant == "off"
    assert enabled is True
