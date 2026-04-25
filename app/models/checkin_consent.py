"""CB-DCI-001 M0-11 — Checkin consent + settings models.

Two tables:

1. ``checkin_consent`` — per-(parent, kid) consent record per spec § 10.
   This table is **owned by M0-2** (#4140), which lands the canonical
   model in ``app/models/dci.py`` alongside the rest of the DCI data
   model. This file declares the same model so M0-11 (which lands
   first) is independently testable; **the integration merge will
   collapse the two definitions** to the M0-2 version (M0-2 wins —
   columns and table name match exactly, so the only refactor needed
   is to update the import path in ``app/services/dci_consent_service.py``
   and remove this file).

2. ``checkin_settings`` — M0-11-specific parent-controlled DCI
   preferences for the ``/settings/account`` DCI section
   (``dci_enabled``, ``muted``, ``kid_push_time``, ``parent_push_time``).
   Lives in its own table to avoid colliding with the spec-§ 10 columns
   M0-2 owns. None of these gate consent; only ``photo_ok``,
   ``voice_ok``, ``ai_ok`` participate in ``assert_dci_consent``.

NOTE: For production Postgres, ``checkin_settings`` needs an
``ALTER TABLE`` migration in ``main.py`` startup per the project
``CLAUDE.md`` migration rules. Tracked in the M0-11 PR description.
"""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
)
from sqlalchemy.sql import func

from app.db.database import Base


class CheckinConsent(Base):
    """Per-(parent, kid) DCI consent record — spec § 10.

    Mirror of the model M0-2 will land in ``app/models/dci.py``. Kept
    here so this stripe is independently testable; integration merge
    will deduplicate against the M0-2 version.
    """

    __tablename__ = "checkin_consent"

    parent_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    kid_id = Column(
        Integer,
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    photo_ok = Column(Boolean, nullable=False, default=False, server_default="FALSE")
    voice_ok = Column(Boolean, nullable=False, default=False, server_default="FALSE")
    ai_ok = Column(Boolean, nullable=False, default=False, server_default="FALSE")
    retention_days = Column(Integer, nullable=False, default=90, server_default="90")
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        PrimaryKeyConstraint("parent_id", "kid_id", name="pk_checkin_consent"),
    )


class CheckinSettings(Base):
    """Per-(parent, kid) M0-11 DCI preferences for /settings/account.

    Additive to spec § 10. None of these fields gate consent; they only
    drive the parent-facing settings UX. Stored in a separate table so
    M0-2's canonical ``checkin_consent`` model (spec-exact) does not
    need to absorb settings-layer columns.
    """

    __tablename__ = "checkin_settings"

    parent_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    kid_id = Column(
        Integer,
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    dci_enabled = Column(Boolean, nullable=False, default=True, server_default="TRUE")
    muted = Column(Boolean, nullable=False, default=False, server_default="FALSE")
    # HH:MM 24h. Defaults from spec § 7: kid 3:15 PM, parent 7:00 PM.
    kid_push_time = Column(String(5), nullable=False, default="15:15", server_default="15:15")
    parent_push_time = Column(String(5), nullable=False, default="19:00", server_default="19:00")
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        PrimaryKeyConstraint("parent_id", "kid_id", name="pk_checkin_settings"),
        Index("ix_checkin_settings_parent", "parent_id"),
        Index("ix_checkin_settings_kid", "kid_id"),
    )
