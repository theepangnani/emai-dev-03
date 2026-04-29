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
        {
            "key": "task_sync_enabled",
            "name": "Task Sync",
            "description": "Auto-create Tasks from Assignment rows and parent email digests (CB-TASKSYNC-001)",
            "enabled": False,
            "variant": "off",
        },
        {
            "key": "tutor_chat_enabled",
            "name": "Tutor Chat (SSE)",
            "description": "CB-TUTOR-002 Phase 1 — POST /api/tutor/chat/stream SSE tutor chat endpoint. Paywall-relevant.",
            "enabled": False,
            "variant": "off",
        },
        {
            "key": "learning_cycle_enabled",
            "name": "Learning Cycle",
            "description": "CB-TUTOR-002 Phase 2 — short learning cycle flow gate. Paywall-relevant.",
            "enabled": False,
            "variant": "off",
        },
        {
            "key": "dci_v1_enabled",
            "name": "Daily Check-In V1",
            "description": (
                "CB-DCI-001 M0 — Daily Check-In Ritual web demo. "
                "Gates the kid `/checkin` flow, parent `/parent/today` summary, "
                "and `POST /api/dci/*` endpoints. OFF by default for the M0 build."
            ),
            "enabled": False,
            "variant": "off",
        },
        {
            "key": "parent.unified_digest_v2",
            "name": "Unified Multi-Kid Email Digest V2",
            "description": (
                "#4012/#4103: Unified multi-kid Email Digest page + single digest per parent "
                "with school-email attribution. ON by default since #4103 — the legacy per-kid "
                "path leaked the wrong child's name into multi-kid parents' digests and was "
                "retired. Ramp via variant: off / on_5 / on_25 / on_50 / on_100."
            ),
            "enabled": True,
            "variant": "on_100",
        },
        {
            "key": "cmcp.enabled",
            "name": "Curriculum Management & Content Platform (CB-CMCP-001)",
            "description": (
                "CB-CMCP-001 M0 — gates the Ontario curriculum REST API "
                "(GET /api/curriculum/*) and downstream CMCP stripes "
                "(CEG extraction, study-guide alignment, board surface). "
                "Default OFF; flip ON in the feature_flags table during M0 "
                "validation. Other CB-CMCP-001 stripes reuse this same flag."
            ),
            "enabled": False,
            "variant": "off",
        },
        {
            "key": "mcp.enabled",
            "name": "MCP Transport (CB-CMCP-001 M2)",
            "description": (
                "CB-CMCP-001 M2-A 2A-2 (#4550): gates the Model Context Protocol "
                "transport router (POST /mcp/initialize, GET /mcp/list_tools, "
                "POST /mcp/call_tool) so LLM clients (Claude Desktop etc.) can "
                "invoke ClassBridge tools. Separate from cmcp.enabled because the "
                "MCP transport is a distinct trust boundary from the REST surface. "
                "Default OFF; flip ON during M2 validation."
            ),
            "enabled": False,
            "variant": "off",
        },
        {
            "key": "theme.bridge_default",
            "name": "Bridge Theme (Force-Apply Default)",
            "description": (
                "CB-THEME-001 #4156: when ON for the current user, ThemeProvider "
                "force-applies the bridge theme on first mount (only when no "
                "explicit theme is stored in localStorage). Subsequent ThemeToggle "
                "flips remain sticky. Variants: off / on_5 / on_25 / on_50 / on_100 / on_for_all."
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
            elif (
                seed["key"] == "parent.unified_digest_v2"
                and existing.variant == "off"
                and existing.enabled is False
            ):
                # #4103 — promote any existing row still pinned to the EXACT original
                # fresh-seed default (enabled=False AND variant="off"). This is the
                # state seeded by #4012 before #4103, so we treat it as a "fresh-seed
                # marker" and force rollout to on_100 on next deploy.
                #
                # Admin overrides are preserved by setting EITHER:
                #   * variant != "off"  (e.g. "on_5" / "on_25" / "on_50" / "on_100"
                #     for partial rollout, or any custom variant string)
                #   * enabled=True with variant="off"  (explicit enabled-but-off)
                # For a permanent disable that survives re-seeds, set variant to a
                # sentinel value such as "off_admin_disabled" so the guard above
                # does not match.
                existing.enabled = True
                existing.variant = "on_100"
                db.commit()
                logger.info(
                    "Promoted feature flag '%s' from off → on_100 (#4103)",
                    seed["key"],
                )
        except Exception:
            db.rollback()
            logger.warning("Could not seed feature flag '%s'", seed["key"])

    return added
