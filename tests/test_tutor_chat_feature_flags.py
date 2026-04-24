"""Tests for `tutor_chat_enabled` and `learning_cycle_enabled` flags (#4066).

Covers:
- `seed_features()` seeds both flags with default OFF.
- `is_feature_enabled(...)` returns False by default.
- Seed is idempotent — running it twice does not duplicate rows or mutate
  existing state.
"""


def _reset_flag(db_session, key: str):
    """Ensure a seeded flag exists and is `enabled=False` before a test."""
    from app.models.feature_flag import FeatureFlag
    from app.services.feature_seed_service import seed_features

    seed_features(db_session)
    flag = (
        db_session.query(FeatureFlag)
        .filter(FeatureFlag.key == key)
        .first()
    )
    if flag is not None and flag.enabled is True:
        flag.enabled = False
        db_session.commit()
    return flag


def test_tutor_chat_enabled_flag_seeded_default_off(db_session):
    """`seed_features()` must add `tutor_chat_enabled` with enabled=False."""
    flag = _reset_flag(db_session, "tutor_chat_enabled")

    assert flag is not None, "tutor_chat_enabled should be seeded"
    assert flag.enabled is False
    assert flag.name == "Tutor Chat"
    assert flag.description == (
        "Gate for CB-TUTOR-002 Phase 1 chat-first Q&A. Paywall-relevant."
    )
    assert flag.variant == "off"


def test_learning_cycle_enabled_flag_seeded_default_off(db_session):
    """`seed_features()` must add `learning_cycle_enabled` with enabled=False."""
    flag = _reset_flag(db_session, "learning_cycle_enabled")

    assert flag is not None, "learning_cycle_enabled should be seeded"
    assert flag.enabled is False
    assert flag.name == "Learning Cycle"
    assert flag.description == "Gate for CB-TUTOR-002 Phase 2 learning-cycle flow."
    assert flag.variant == "off"


def test_is_feature_enabled_returns_false_for_tutor_chat_by_default(db_session):
    """`is_feature_enabled('tutor_chat_enabled')` must be False on a fresh seed."""
    from app.services.feature_flag_service import is_feature_enabled

    _reset_flag(db_session, "tutor_chat_enabled")

    assert is_feature_enabled("tutor_chat_enabled", db=db_session) is False


def test_is_feature_enabled_returns_false_for_learning_cycle_by_default(db_session):
    """`is_feature_enabled('learning_cycle_enabled')` must be False on a fresh seed."""
    from app.services.feature_flag_service import is_feature_enabled

    _reset_flag(db_session, "learning_cycle_enabled")

    assert is_feature_enabled("learning_cycle_enabled", db=db_session) is False


def test_tutor_chat_seed_is_idempotent(db_session):
    """Running `seed_features()` twice must not duplicate or mutate either flag."""
    from app.models.feature_flag import FeatureFlag
    from app.services.feature_seed_service import seed_features

    for key in ("tutor_chat_enabled", "learning_cycle_enabled"):
        _reset_flag(db_session, key)
        first = (
            db_session.query(FeatureFlag)
            .filter(FeatureFlag.key == key)
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
            .filter(FeatureFlag.key == key)
            .count()
        )
        assert count == 1, f"Seed must not duplicate {key}"

        second = (
            db_session.query(FeatureFlag)
            .filter(FeatureFlag.key == key)
            .first()
        )
        assert second is not None
        assert second.id == first_id
        assert second.description == first_description
        assert second.enabled == first_enabled
