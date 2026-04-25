/**
 * CB-BRIDGE-002 — selected-kid hero card (#4113).
 *
 * Renders the spotlight strip for a selected child: avatar, name+grade,
 * sub line (school + invite status), 3-up vitals (classes / open tasks /
 * on-track), primary "Open Tutor" CTA, and an overflow kebab.
 *
 * Presentational — all callbacks come from the parent. XP is intentionally
 * omitted in this stripe; it lands in PR 4 alongside ChildXpStats restyle.
 */
import type { ChildSummary } from '../../api/client';
import { OnTrackBadge } from '../OnTrackBadge';
import { KidActionsMenu } from './KidActionsMenu';
import { getInitial } from './util';

interface KidHeroProps {
  child: ChildSummary;
  color: string;
  onOpenTutor: () => void;
  onEdit: () => void;
  onExport: () => void;
  onResetPassword?: () => void;
  onAwardXp?: () => void;
  onResendInvite?: () => void;
  onCopyInviteLink?: () => void;
  onRemove: () => void;
  resending?: boolean;
  resendSuccess?: boolean;
  copyInviteSuccess?: boolean;
}

export function KidHero({
  child,
  color,
  onOpenTutor,
  onEdit,
  onExport,
  onResetPassword,
  onAwardXp,
  onResendInvite,
  onCopyInviteLink,
  onRemove,
  resending,
  resendSuccess,
  copyInviteSuccess,
}: KidHeroProps) {
  const status = child.invite_status;
  const statusLabel =
    status === 'active' ? 'Active' : status === 'pending' ? 'Pending link' : status === 'email_unverified' ? 'Unverified' : null;

  return (
    <section className="bridge-hero" aria-label={`${child.full_name} hero`}>
      <div className="bridge-hero-left">
        <div className="bridge-hero-avatar" style={{ background: color }}>
          {getInitial(child.full_name)}
        </div>
        <div>
          <div className="bridge-hero-name">
            {child.full_name}
            {child.grade_level != null && (
              <span className="bridge-hero-grade">Grade {child.grade_level}</span>
            )}
          </div>
          <div className="bridge-hero-sub">
            {child.school_name && <span>{child.school_name}</span>}
            {child.school_name && statusLabel && <span className="bridge-hero-dotsep" aria-hidden="true" />}
            {statusLabel && (
              <span className={`bridge-hero-status bridge-hero-status--${status}`}>● {statusLabel}</span>
            )}
          </div>
        </div>
      </div>

      <div className="bridge-hero-right">
        <div className="bridge-hero-vitals" role="list">
          <div className="bridge-vital" role="listitem">
            <div className="bridge-vital-label">Classes</div>
            <div className="bridge-vital-value">{child.course_count}</div>
          </div>
          <div className="bridge-vital" role="listitem">
            <div className="bridge-vital-label">Open tasks</div>
            <div className="bridge-vital-value">{child.active_task_count}</div>
          </div>
          <div className="bridge-vital bridge-vital--status" role="listitem">
            <div className="bridge-vital-label">Status</div>
            <div className="bridge-vital-value">
              <OnTrackBadge studentId={child.student_id} />
            </div>
          </div>
        </div>

        <div className="bridge-hero-cta">
          <KidActionsMenu
            onEdit={onEdit}
            onExport={onExport}
            onResetPassword={onResetPassword}
            onAwardXp={onAwardXp}
            onResendInvite={onResendInvite}
            onCopyInviteLink={onCopyInviteLink}
            onRemove={onRemove}
            resending={resending}
            resendSuccess={resendSuccess}
            copyInviteSuccess={copyInviteSuccess}
          />
          <button type="button" className="bridge-btn-primary" onClick={onOpenTutor}>
            Open Tutor <span className="bridge-btn-arrow" aria-hidden="true">→</span>
          </button>
        </div>
      </div>
    </section>
  );
}
