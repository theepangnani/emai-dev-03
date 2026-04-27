/**
 * CB-BRIDGE-002 — selected-kid hero card (#4113).
 *
 * Renders the spotlight strip for a selected child: avatar, name+grade,
 * sub line (school + invite status), 3-up vitals (classes / open tasks /
 * on-track), primary "Open Tutor" CTA, and an overflow kebab.
 *
 * Presentational — all callbacks come from the parent. XP is intentionally
 * omitted in this stripe; it lands in PR 4 alongside ChildXpStats restyle.
 *
 * CB-KIDPHOTO-001 (#4301): clicking the avatar opens a file picker to
 * upload a profile photo. Photo replaces the initial. Hover overlays a
 * camera icon; loading shows a spinner; failures surface as toasts.
 */
import { useRef, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import type { ChildSummary } from '../../api/client';
import { uploadKidPhoto } from '../../api/kidPhoto';
import { useToast } from '../Toast';
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
  onQuizHistory?: () => void;
  onResendInvite?: () => void;
  onCopyInviteLink?: () => void;
  onRemove: () => void;
  resending?: boolean;
  resendSuccess?: boolean;
  copyInviteSuccess?: boolean;
  /** CB-KIDPHOTO-001 (#4301) — fired after a successful photo upload so the
   * page can refresh its children list. Receives the new photo URL. */
  onPhotoChange?: (newUrl: string) => void;
}

export function KidHero({
  child,
  color,
  onOpenTutor,
  onEdit,
  onExport,
  onResetPassword,
  onAwardXp,
  onQuizHistory,
  onResendInvite,
  onCopyInviteLink,
  onRemove,
  resending,
  resendSuccess,
  copyInviteSuccess,
  onPhotoChange,
}: KidHeroProps) {
  const status = child.invite_status;
  const statusLabel =
    status === 'active' ? 'Active' : status === 'pending' ? 'Pending link' : status === 'email_unverified' ? 'Unverified' : null;

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const { toast } = useToast();
  const [optimisticUrl, setOptimisticUrl] = useState<string | null>(null);

  const photoUrl = optimisticUrl ?? child.profile_photo_url ?? null;

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadKidPhoto(child.student_id, file),
    onSuccess: (data) => {
      setOptimisticUrl(data.profile_photo_url);
      toast('Profile photo updated', 'success');
      onPhotoChange?.(data.profile_photo_url);
    },
    onError: (err: unknown) => {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast(detail || 'Could not upload photo. Please try again.', 'error');
    },
  });

  const handleAvatarClick = () => {
    if (uploadMutation.isPending) return;
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    // Reset so selecting the same file twice still fires onChange.
    e.target.value = '';
    if (!file) return;
    uploadMutation.mutate(file);
  };

  return (
    <section className="bridge-hero" aria-label={`${child.full_name} hero`}>
      <div className="bridge-hero-left">
        <button
          type="button"
          className="bridge-hero-avatar"
          style={{ background: photoUrl ? 'transparent' : color }}
          onClick={handleAvatarClick}
          disabled={uploadMutation.isPending}
          aria-label={`Change profile photo for ${child.full_name}`}
        >
          {photoUrl ? (
            <img src={photoUrl} alt="" className="bridge-hero-avatar-img" />
          ) : (
            <span className="bridge-hero-avatar-initial">{getInitial(child.full_name)}</span>
          )}
          {uploadMutation.isPending ? (
            <span className="bridge-hero-avatar-spinner" aria-hidden="true" />
          ) : (
            <span className="bridge-hero-avatar-overlay" aria-hidden="true">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
                <circle cx="12" cy="13" r="4" />
              </svg>
            </span>
          )}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          onChange={handleFileChange}
          style={{ display: 'none' }}
          aria-hidden="true"
          tabIndex={-1}
        />
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
            onQuizHistory={onQuizHistory}
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
