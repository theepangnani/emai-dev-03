"""Drift detector for CB-DCI-001 flag constants (#4175).

Asserts that every ``DCI_*`` flag-key constant exported from
``app.services.feature_flag_service`` has a matching seed row in
``app.services.feature_seed_service.seed_features``. Catches the silent
"constant added but seed forgotten" failure mode that the existing
single-key equality check misses.
"""

from __future__ import annotations

import inspect


def test_every_dci_constant_has_seed_row():
    """Every ``DCI_*`` flag constant must appear as a key in the seed list."""
    import app.services.feature_flag_service as ffs
    from app.services import feature_seed_service

    dci_constants = {
        value
        for name, value in vars(ffs).items()
        if name.startswith("DCI_") and isinstance(value, str)
    }
    assert dci_constants, "Expected at least one DCI_* flag constant"

    seed_src = inspect.getsource(feature_seed_service.seed_features)
    missing = [key for key in dci_constants if f'"{key}"' not in seed_src]
    assert not missing, (
        f"DCI_* constants without a matching seed row: {sorted(missing)}"
    )
