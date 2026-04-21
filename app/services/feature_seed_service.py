"""Seed the feature_flags table with default features.

Only runs if the table is empty (idempotent).
"""

import logging

from sqlalchemy.orm import Session

from app.models.feature_flag import FeatureFlag

logger = logging.getLogger(__name__)


def seed_features(db: Session) -> int:
    """Seed default feature flags.

    Base flags are only seeded when the table is empty (legacy behavior).
    Per-key flags (e.g. demo_landing_v1_1) are seeded idempotently so
    they can be added to existing environments without wiping rows.
    """
    added = 0
    try:
        if db.query(FeatureFlag).count() == 0:
            base_features = [
                FeatureFlag(
                    key="school_board_connectivity",
                    name="School Board Connectivity",
                    description="Connect to school board systems for announcements and data sharing",
                    enabled=False,
                ),
                FeatureFlag(
                    key="report_cards",
                    name="Report Cards",
                    description="Report card upload and AI analysis for parents and students",
                    enabled=False,
                ),
                FeatureFlag(
                    key="analytics",
                    name="Analytics",
                    description="Analytics dashboard for parents, students, and admins",
                    enabled=False,
                ),
            ]
            db.add_all(base_features)
            db.commit()
            added += len(base_features)
            logger.info("Seeded %d default feature flags", len(base_features))
    except Exception:
        db.rollback()
        logger.warning("Could not seed feature flags (table may not exist yet)")
        return added

    # Idempotent per-key seeds (safe to run on every startup)
    per_key_seeds = [
        {
            "key": "demo_landing_v1_1",
            "name": "Demo Landing v1.1",
            "description": "CB-DEMO-001: Instant Trial & Demo Experience landing page (A/B-gated)",
            "enabled": False,
            "variant": "off",
        },
        {
            "key": "landing_v2",
            "name": "Landing Page v2",
            "description": (
                "CB-LAND-001: Mindgrasp-inspired landing page redesign. "
                "Variant controls percentage rollout: off / on_5 / on_25 / on_50 / on_100. "
                "When on, HomeRedirect renders LandingPageV2 for anonymous visitors."
            ),
            "enabled": False,
            "variant": "off",
        },
    ]

    for seed in per_key_seeds:
        try:
            existing = db.query(FeatureFlag).filter(FeatureFlag.key == seed["key"]).first()
            if existing is None:
                db.add(FeatureFlag(
                    key=seed["key"],
                    name=seed["name"],
                    description=seed["description"],
                    enabled=seed["enabled"],
                    variant=seed["variant"],
                ))
                db.commit()
                added += 1
                logger.info("Seeded feature flag '%s' with variant='%s'", seed["key"], seed["variant"])
        except Exception:
            db.rollback()
            logger.warning("Could not seed feature flag '%s'", seed["key"])

    return added
