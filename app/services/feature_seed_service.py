"""Seed the feature_flags table with default features.

Only runs if the table is empty (idempotent).
"""

import logging

from sqlalchemy.orm import Session

from app.models.feature_flag import FeatureFlag

logger = logging.getLogger(__name__)


def seed_features(db: Session) -> int:
    """Seed default feature flags if table is empty."""
    try:
        if db.query(FeatureFlag).count() > 0:
            return 0

        features = [
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
        db.add_all(features)
        db.commit()
        logger.info("Seeded %d default feature flags", len(features))
        return len(features)
    except Exception:
        db.rollback()
        logger.warning("Could not seed feature flags (table may not exist yet)")
        return 0
