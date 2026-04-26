"""Tests for the `dci_v1_enabled` feature flag (CB-DCI-001 M0-3, #4141).

Covers:
- `seed_features()` seeds `dci_v1_enabled` with default OFF.
- `is_feature_enabled('dci_v1_enabled')` returns False by default.
- `is_dci_enabled()` convenience wrapper mirrors the underlying helper.
- Flipping `enabled=True` flows through both helpers.
- Seed is idempotent — running it twice does not duplicate rows or
  mutate existing state.
- The exported `DCI_V1_ENABLED` constant matches the seeded key (catches
  silent typo drift between the constant and the seed row).
"""


def _reset_dci_flag(db_session):
    """Ensure `dci_v1_enabled` exists and is enabled=False before a test."""
    from app.models.feature_flag import FeatureFlag
    from app.services.feature_seed_service import seed_features

    seed_features(db_session)
    flag = (
        db_session.query(FeatureFlag)
        .filter(FeatureFlag.key == "dci_v1_enabled")
        .first()
    )
    if flag is not None and flag.enabled is True:
        flag.enabled = False
        db_session.commit()
    return flag


def test_dci_v1_enabled_flag_seeded_default_off(db_session):
    """`seed_features()` must add `dci_v1_enabled` with enabled=False."""
    flag = _reset_dci_flag(db_session)

    assert flag is not None, "dci_v1_enabled should be seeded"
    assert flag.enabled is False
    assert flag.name == "Daily Check-In V1"
    assert "CB-DCI-001" in flag.description
    assert flag.variant == "off"


def test_is_feature_enabled_returns_false_for_dci_by_default(db_session):
    """`is_feature_enabled('dci_v1_enabled')` must be False on a fresh seed."""
    from app.services.feature_flag_service import is_feature_enabled

    _reset_dci_flag(db_session)

    assert is_feature_enabled("dci_v1_enabled", db=db_session) is False


def test_is_dci_enabled_helper_returns_false_by_default(db_session):
    """`is_dci_enabled()` convenience wrapper mirrors the default-OFF state."""
    from app.services.feature_flag_service import is_dci_enabled

    _reset_dci_flag(db_session)

    assert is_dci_enabled(db=db_session) is False


def test_is_dci_enabled_helper_returns_true_when_toggled_on(db_session):
    """Flipping `enabled=True` must propagate through `is_dci_enabled()`."""
    from app.services.feature_flag_service import is_dci_enabled, is_feature_enabled

    flag = _reset_dci_flag(db_session)
    assert flag is not None
    flag.enabled = True
    db_session.commit()

    try:
        assert is_feature_enabled("dci_v1_enabled", db=db_session) is True
        assert is_dci_enabled(db=db_session) is True
    finally:
        # Reset so sibling tests see the default-off state even if this
        # test aborts between toggle-on and assertion.
        flag.enabled = False
        db_session.commit()


def test_dci_constant_matches_seed_key():
    """`DCI_V1_ENABLED` constant must equal the literal seeded key."""
    from app.services.feature_flag_service import DCI_V1_ENABLED

    assert DCI_V1_ENABLED == "dci_v1_enabled"


def test_dci_seed_is_idempotent(db_session):
    """Running `seed_features()` twice must not duplicate or mutate the row."""
    from app.models.feature_flag import FeatureFlag
    from app.services.feature_seed_service import seed_features

    _reset_dci_flag(db_session)
    first = (
        db_session.query(FeatureFlag)
        .filter(FeatureFlag.key == "dci_v1_enabled")
        .first()
    )
    assert first is not None
    first_id = first.id
    first_description = first.description
    first_enabled = first.enabled

    seed_features(db_session)
    db_session.expire_all()

    count = (
        db_session.query(FeatureFlag)
        .filter(FeatureFlag.key == "dci_v1_enabled")
        .count()
    )
    assert count == 1, "Seed must not duplicate dci_v1_enabled"

    second = (
        db_session.query(FeatureFlag)
        .filter(FeatureFlag.key == "dci_v1_enabled")
        .first()
    )
    assert second is not None
    assert second.id == first_id
    assert second.description == first_description
    assert second.enabled == first_enabled
