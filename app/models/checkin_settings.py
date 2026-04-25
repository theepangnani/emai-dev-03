"""CB-DCI-001 M0-11 — Checkin settings model.

Per-(parent, kid) DCI preferences for the ``/settings/account`` DCI section
(``dci_enabled``, ``muted``, ``kid_push_time``, ``parent_push_time``).

Lives in its own table — separate from the spec § 10 ``checkin_consent``
table that M0-2 owns in ``app/models/dci.py``. None of these fields gate
consent; only ``photo_ok``, ``voice_ok``, ``ai_ok`` (on the M0-2
``CheckinConsent`` model) participate in ``assert_dci_consent``.

NOTE: For production Postgres, ``checkin_settings`` needs an
``ALTER TABLE`` migration in ``main.py`` startup per the project
``CLAUDE.md`` migration rules.
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
