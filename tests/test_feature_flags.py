"""Tests for the `task_sync_enabled` feature flag seed and helper (#3914).

Covers:
- `seed_features()` seeds `task_sync_enabled` with default OFF.
- `is_feature_enabled("task_sync_enabled")` returns False by default.
- Seed is idempotent — running it twice does not duplicate rows or
  mutate existing state.

Note: the DB-backed `feature_flags` row persists for the session-scoped
test app; each test that cares about the default-off state resets the
row at the start to avoid ordering sensitivity.
"""


def _reset_task_sync_flag(db_session):
    """Ensure `task_sync_enabled` exists and is enabled=False before a test."""
    from app.models.feature_flag import FeatureFlag
    from app.services.feature_seed_service import seed_features

    seed_features(db_session)
    flag = (
        db_session.query(FeatureFlag)
        .filter(FeatureFlag.key == "task_sync_enabled")
        .first()
    )
    if flag is not None and flag.enabled is True:
        flag.enabled = False
        db_session.commit()
    return flag


def test_task_sync_enabled_flag_seeded_default_off(db_session):
    """`seed_features()` must add `task_sync_enabled` with enabled=False."""
    flag = _reset_task_sync_flag(db_session)

    assert flag is not None, "task_sync_enabled should be seeded"
    assert flag.enabled is False
    assert flag.name == "Task Sync"
    assert flag.description == (
        "Auto-create Tasks from Assignment rows and parent email digests "
        "(CB-TASKSYNC-001)"
    )
    assert flag.variant == "off"


def test_is_feature_enabled_returns_false_for_task_sync_by_default(db_session):
    """`is_feature_enabled('task_sync_enabled')` must be False on a fresh seed."""
    from app.services.feature_flag_service import is_feature_enabled

    _reset_task_sync_flag(db_session)

    assert is_feature_enabled("task_sync_enabled", db=db_session) is False


def test_is_feature_enabled_returns_false_for_unknown_key(db_session):
    """Unknown / empty / whitespace-only keys fail closed — return False."""
    from app.services.feature_flag_service import is_feature_enabled

    assert is_feature_enabled("does_not_exist_" + "xyz", db=db_session) is False
    assert is_feature_enabled("", db=db_session) is False
    assert is_feature_enabled("   ", db=db_session) is False


def test_is_feature_enabled_returns_true_when_toggled_on(db_session):
    """Flipping `enabled=True` flows through to the helper."""
    from app.services.feature_flag_service import is_feature_enabled

    flag = _reset_task_sync_flag(db_session)
    assert flag is not None
    flag.enabled = True
    db_session.commit()

    try:
        assert is_feature_enabled("task_sync_enabled", db=db_session) is True
    finally:
        # Reset so sibling tests see the default-off state even if this
        # test aborts between toggle-on and assertion.
        flag.enabled = False
        db_session.commit()


def test_seed_is_idempotent(db_session):
    """Running `seed_features()` twice must not duplicate or mutate the row."""
    from app.models.feature_flag import FeatureFlag
    from app.services.feature_seed_service import seed_features

    _reset_task_sync_flag(db_session)
    first = (
        db_session.query(FeatureFlag)
        .filter(FeatureFlag.key == "task_sync_enabled")
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
        .filter(FeatureFlag.key == "task_sync_enabled")
        .count()
    )
    assert count == 1, "Seed must not duplicate task_sync_enabled"

    second = (
        db_session.query(FeatureFlag)
        .filter(FeatureFlag.key == "task_sync_enabled")
        .first()
    )
    assert second is not None
    assert second.id == first_id
    assert second.description == first_description
    assert second.enabled == first_enabled
