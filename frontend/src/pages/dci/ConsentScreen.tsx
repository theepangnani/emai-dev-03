// CB-DCI-001 M0-11 — Consent screen (#4148)
//
// Spec: docs/design/CB-DCI-001-daily-checkin.md § 11.
//
// Per-kid consent flow shown on first /checkin or /parent/today access.
// Togglable: photo OK, voice OK, AI processing, retention (90d/1y/3y).
//
// All routing wiring (when to show this screen on /checkin or
// /parent/today) is owned by M0-9 / M0-10. This component exposes a
// single self-contained screen the route gates can render.

import { useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';

import type { ChildSummary } from '../../api/parent';
import { parentApi } from '../../api/parent';
import { Bill194Disclosure } from '../../components/dci/Bill194Disclosure';
import {
  useDciConsent,
  useUpsertDciConsent,
} from '../../hooks/useDciConsent';
import type { DciConsent } from '../../api/dciConsent';

const RETENTION_OPTIONS: { value: number; label: string }[] = [
  { value: 90, label: '90 days' },
  { value: 365, label: '1 year' },
  { value: 1095, label: '3 years' },
];

const containerStyle: React.CSSProperties = {
  maxWidth: 560,
  margin: '32px auto',
  padding: '24px',
  background: '#fff',
  border: '1px solid #e5e7eb',
  borderRadius: 16,
  fontFamily: 'inherit',
  color: '#111827',
};

const headingStyle: React.CSSProperties = {
  fontSize: 22,
  fontWeight: 700,
  margin: '0 0 8px',
  color: '#0f172a',
};

const subtleStyle: React.CSSProperties = {
  color: '#6b7280',
  fontSize: 14,
  margin: '0 0 16px',
};

const sectionStyle: React.CSSProperties = {
  marginTop: 20,
  paddingTop: 16,
  borderTop: '1px solid #f3f4f6',
};

const toggleRow: React.CSSProperties = {
  display: 'flex',
  alignItems: 'flex-start',
  gap: 12,
  margin: '12px 0',
};

const toggleLabel: React.CSSProperties = {
  fontWeight: 600,
  fontSize: 14,
};

const toggleDesc: React.CSSProperties = {
  color: '#6b7280',
  fontSize: 12,
  margin: '2px 0 0',
};

const buttonRow: React.CSSProperties = {
  display: 'flex',
  gap: 12,
  marginTop: 24,
  justifyContent: 'flex-end',
};

const primaryButton: React.CSSProperties = {
  background: '#1e293b',
  color: '#fff',
  border: 'none',
  padding: '10px 20px',
  borderRadius: 8,
  fontWeight: 600,
  cursor: 'pointer',
};

const secondaryButton: React.CSSProperties = {
  background: '#fff',
  color: '#1e293b',
  border: '1px solid #cbd5e1',
  padding: '10px 20px',
  borderRadius: 8,
  fontWeight: 500,
  cursor: 'pointer',
};

interface ConsentEditorProps {
  kid: ChildSummary;
  initialConsent: DciConsent;
  onSaved: (kidId: number) => void;
}

/**
 * Inner editor — re-mounted (via React `key`) whenever the active kid
 * or fetched consent changes, so local edit-buffer state initialises
 * cleanly from props without setState-in-effect.
 */
function ConsentEditor({ kid, initialConsent, onSaved }: ConsentEditorProps) {
  const upsert = useUpsertDciConsent();
  const [photoOk, setPhotoOk] = useState(initialConsent.photo_ok);
  const [voiceOk, setVoiceOk] = useState(initialConsent.voice_ok);
  const [aiOk, setAiOk] = useState(initialConsent.ai_ok);
  const [retentionDays, setRetentionDays] = useState<number>(
    initialConsent.retention_days,
  );
  const [savedAt, setSavedAt] = useState<number | null>(null);

  const isSaving = upsert.isPending;
  const canSave = !isSaving;

  function handleSave() {
    upsert.mutate(
      {
        kid_id: kid.student_id,
        photo_ok: photoOk,
        voice_ok: voiceOk,
        ai_ok: aiOk,
        retention_days: retentionDays,
      },
      {
        onSuccess: () => {
          setSavedAt(Date.now());
          onSaved(kid.student_id);
        },
      },
    );
  }

  return (
    <>
      <fieldset
        style={{ ...sectionStyle, border: 'none', padding: 0, margin: 0, marginTop: 20 }}
        disabled={isSaving}
      >
        <legend style={{ ...toggleLabel, fontSize: 16 }}>
          What can {kid.full_name} share?
        </legend>

        <div style={toggleRow}>
          <input
            id="dci-consent-photo"
            type="checkbox"
            checked={photoOk}
            onChange={(e) => setPhotoOk(e.target.checked)}
            style={{ marginTop: 4 }}
          />
          <div>
            <label htmlFor="dci-consent-photo" style={toggleLabel}>
              Photos OK
            </label>
            <p style={toggleDesc}>
              Snap photos of handouts, board work, or notebooks.
            </p>
          </div>
        </div>

        <div style={toggleRow}>
          <input
            id="dci-consent-voice"
            type="checkbox"
            checked={voiceOk}
            onChange={(e) => setVoiceOk(e.target.checked)}
            style={{ marginTop: 4 }}
          />
          <div>
            <label htmlFor="dci-consent-voice" style={toggleLabel}>
              Voice OK
            </label>
            <p style={toggleDesc}>Record a short voice note about today.</p>
          </div>
        </div>

        <div style={toggleRow}>
          <input
            id="dci-consent-ai"
            type="checkbox"
            checked={aiOk}
            onChange={(e) => setAiOk(e.target.checked)}
            style={{ marginTop: 4 }}
          />
          <div>
            <label htmlFor="dci-consent-ai" style={toggleLabel}>
              AI processing OK
            </label>
            <p style={toggleDesc}>
              Allow AI to summarize the check-in for your evening
              digest. Required to use Daily Check-In.
            </p>
            {!aiOk && (
              <p
                style={{ ...toggleDesc, color: '#b45309', marginTop: 4 }}
                data-testid="dci-consent-ai-warning"
                role="status"
              >
                Daily Check-In stays paused for {kid.full_name} while
                AI processing is off.
              </p>
            )}
          </div>
        </div>
      </fieldset>

      <div style={sectionStyle}>
        <label htmlFor="dci-consent-retention" style={toggleLabel}>
          How long should we keep this data?
        </label>
        <p style={toggleDesc}>
          You can delete or change this any time in Account Settings.
        </p>
        <select
          id="dci-consent-retention"
          value={retentionDays}
          onChange={(e) => setRetentionDays(Number(e.target.value))}
          style={{
            display: 'block',
            marginTop: 8,
            padding: '8px 10px',
            borderRadius: 6,
            border: '1px solid #cbd5e1',
            fontSize: 14,
            minWidth: 220,
          }}
          disabled={isSaving}
        >
          {RETENTION_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {upsert.isError && (
        <p
          role="alert"
          style={{ color: '#b91c1c', marginTop: 12, fontSize: 13 }}
        >
          Couldn't save consent. Please try again.
        </p>
      )}
      {savedAt != null && !upsert.isError && (
        <p
          role="status"
          style={{ color: '#047857', marginTop: 12, fontSize: 13 }}
          data-testid="dci-consent-saved"
        >
          Saved.
        </p>
      )}

      <div style={buttonRow}>
        <button
          type="button"
          style={{
            ...primaryButton,
            opacity: canSave ? 1 : 0.6,
            cursor: canSave ? 'pointer' : 'not-allowed',
          }}
          onClick={handleSave}
          disabled={!canSave}
          data-testid="dci-consent-save"
        >
          {isSaving ? 'Saving…' : 'Save consent'}
        </button>
      </div>
    </>
  );
}

export interface ConsentScreenProps {
  /** Optional kid id to start on. If omitted, the first linked kid is used. */
  initialKidId?: number;
  /** Override for which kids to show. Defaults to all kids linked to the parent. */
  kids?: ChildSummary[];
  /** Called after the parent saves a consent row. */
  onComplete?: (kidId: number) => void;
  /** Where to navigate on cancel. Defaults to history back. */
  onCancel?: () => void;
}

/**
 * Per-kid DCI consent screen.
 *
 * Shown on first /checkin or /parent/today access — each kid must have
 * a saved consent row before any DCI write can proceed.
 */
export function ConsentScreen({
  initialKidId,
  kids: kidsOverride,
  onComplete,
  onCancel,
}: ConsentScreenProps) {
  const navigate = useNavigate();
  // M0-13 (#4260): when routed at /dci/consent we honour ?return_to= so the
  // parent lands back on /checkin or /parent/today after granting consent.
  // Only same-origin relative paths are accepted to prevent open-redirect.
  const [searchParams] = useSearchParams();
  const returnTo = useMemo(() => {
    const raw = searchParams.get('return_to');
    if (!raw) return null;
    // Reject anything that isn't a same-origin relative path. Must start
    // with a single `/` (not `//` or `/\\`) and have no scheme/host.
    if (!raw.startsWith('/') || raw.startsWith('//') || raw.startsWith('/\\')) {
      return null;
    }
    return raw;
  }, [searchParams]);
  const childrenQuery = useQuery<ChildSummary[]>({
    queryKey: ['dciConsent', 'kidsForConsent'],
    queryFn: parentApi.getChildren,
    enabled: !kidsOverride,
  });
  const kids = useMemo(
    () => kidsOverride ?? childrenQuery.data ?? [],
    [kidsOverride, childrenQuery.data],
  );
  const defaultKidId = kids.length > 0 ? kids[0].student_id : null;
  const [explicitKidId, setExplicitKidId] = useState<number | null>(
    initialKidId ?? null,
  );
  const activeKidId = explicitKidId ?? defaultKidId;

  const consentQuery = useDciConsent(activeKidId);

  const activeKid = useMemo(
    () => kids.find((k) => k.student_id === activeKidId) ?? null,
    [kids, activeKidId],
  );

  function handleCancel() {
    if (onCancel) {
      onCancel();
    } else {
      navigate(-1);
    }
  }

  if (childrenQuery.isLoading && !kidsOverride) {
    return (
      <div style={containerStyle} role="status">
        Loading…
      </div>
    );
  }

  if (kids.length === 0) {
    return (
      <div style={containerStyle}>
        <h1 style={headingStyle}>Daily Check-In consent</h1>
        <p style={subtleStyle}>
          You don't have any kids linked yet. Link a child first, then come
          back to set Daily Check-In consent.
        </p>
        <div style={buttonRow}>
          <button type="button" style={secondaryButton} onClick={handleCancel}>
            Back
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={containerStyle} data-testid="dci-consent-screen">
      <h1 style={headingStyle}>Daily Check-In consent</h1>
      <p style={subtleStyle}>
        Choose what your child can share during their daily 60-second
        check-in. You can change these any time in Account Settings.
      </p>

      <Bill194Disclosure />

      {kids.length > 1 && (
        <div style={sectionStyle}>
          <label htmlFor="dci-consent-kid" style={toggleLabel}>
            Kid
          </label>
          <select
            id="dci-consent-kid"
            value={activeKidId ?? ''}
            onChange={(e) => setExplicitKidId(Number(e.target.value))}
            style={{
              display: 'block',
              marginTop: 6,
              padding: '8px 10px',
              borderRadius: 6,
              border: '1px solid #cbd5e1',
              fontSize: 14,
              minWidth: 220,
            }}
          >
            {kids.map((k) => (
              <option key={k.student_id} value={k.student_id}>
                {k.full_name}
              </option>
            ))}
          </select>
        </div>
      )}

      {consentQuery.isLoading && (
        <p style={{ ...subtleStyle, marginTop: 16 }} role="status">
          Loading consent…
        </p>
      )}

      {activeKid && consentQuery.data && (
        <ConsentEditor
          // Re-mount editor when the active kid (or the loaded snapshot) changes
          // so the local edit-buffer state initialises from the new data
          // without needing a setState-in-effect.
          key={`${activeKid.student_id}:${consentQuery.data.kid_id}`}
          kid={activeKid}
          initialConsent={consentQuery.data}
          onSaved={(kidId) => {
            onComplete?.(kidId);
            // M0-13 (#4260): only navigate when this screen is routed
            // standalone (no `onComplete` override). When embedded in a
            // settings page the host owns navigation. Validated return_to
            // wins; falls back to `/` so the parent never gets stuck.
            if (!onComplete) {
              navigate(returnTo ?? '/', { replace: true });
            }
          }}
        />
      )}

      <div style={buttonRow}>
        <button type="button" style={secondaryButton} onClick={handleCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}

export default ConsentScreen;
