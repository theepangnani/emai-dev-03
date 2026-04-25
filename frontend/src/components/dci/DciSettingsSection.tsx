// CB-DCI-001 M0-11 — DCI section for /settings/account (#4148)
//
// Spec: docs/design/CB-DCI-001-daily-checkin.md § 11.
//
// Mounted as a self-contained <section> on AccountSettingsPage. Additive
// only — does not refactor any existing settings sections.
//
// Surfaces (per kid):
//   - DCI toggle (dci_enabled)
//   - Mute toggle (muted)
//   - Retention slider (90 / 365 / 1095 days)
//   - Push time pickers (kid 3:15 PM, parent 7:00 PM defaults)
// No actual push wiring in M0; preferences persist only.

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { parentApi, type ChildSummary } from '../../api/parent';
import {
  useDciConsentList,
  useUpsertDciConsent,
} from '../../hooks/useDciConsent';
import type { DciConsent } from '../../api/dciConsent';

const RETENTION_OPTIONS: { value: number; label: string }[] = [
  { value: 90, label: '90 days' },
  { value: 365, label: '1 year' },
  { value: 1095, label: '3 years' },
];

const sectionStyle: React.CSSProperties = {
  marginBottom: 24,
};

const kidCardStyle: React.CSSProperties = {
  border: '1px solid #e5e7eb',
  borderRadius: 12,
  padding: 16,
  marginTop: 12,
  background: '#fafafa',
};

const rowStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 10,
  marginTop: 10,
  flexWrap: 'wrap',
};

const labelStyle: React.CSSProperties = {
  fontWeight: 500,
  fontSize: 14,
};

const helpStyle: React.CSSProperties = {
  color: '#6b7280',
  fontSize: 12,
  margin: '4px 0 0',
};

interface KidConsentRowProps {
  kid: ChildSummary;
  consent: DciConsent;
}

function KidConsentRow({ kid, consent }: KidConsentRowProps) {
  const upsert = useUpsertDciConsent();

  // Local edit buffer for time pickers; toggles persist on change for snappy UX.
  // Parent re-mounts this component (via React `key`) whenever the upstream
  // consent snapshot changes, so initial values come from props directly
  // and we don't need a setState-in-effect to resync.
  const [kidTime, setKidTime] = useState(consent.kid_push_time);
  const [parentTime, setParentTime] = useState(consent.parent_push_time);
  const [retention, setRetention] = useState<number>(consent.retention_days);

  const isSaving = upsert.isPending;

  function update(patch: Parameters<typeof upsert.mutate>[0]) {
    upsert.mutate(patch);
  }

  return (
    <div style={kidCardStyle} data-testid={`dci-settings-kid-${kid.student_id}`}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <strong style={{ fontSize: 15 }}>{kid.full_name}</strong>
        {isSaving && <span style={{ fontSize: 12, color: '#6b7280' }}>Saving…</span>}
      </div>

      {/* DCI enabled toggle */}
      <label style={{ ...rowStyle, cursor: 'pointer' }}>
        <input
          type="checkbox"
          checked={consent.dci_enabled}
          disabled={isSaving}
          onChange={(e) =>
            update({ kid_id: kid.student_id, dci_enabled: e.target.checked })
          }
          style={{ width: 16, height: 16 }}
        />
        <span style={labelStyle}>Enable Daily Check-In for this kid</span>
      </label>

      {/* Mute toggle */}
      <label style={{ ...rowStyle, cursor: 'pointer' }}>
        <input
          type="checkbox"
          checked={consent.muted}
          disabled={isSaving}
          onChange={(e) =>
            update({ kid_id: kid.student_id, muted: e.target.checked })
          }
          style={{ width: 16, height: 16 }}
        />
        <span style={labelStyle}>Mute reminders</span>
      </label>
      <p style={helpStyle}>
        Pauses kid + parent push reminders without disabling check-ins.
      </p>

      {/* Retention */}
      <div style={{ marginTop: 14 }}>
        <label htmlFor={`dci-retention-${kid.student_id}`} style={labelStyle}>
          Data retention
        </label>
        <p style={helpStyle}>How long we keep this kid's check-in data.</p>
        <input
          id={`dci-retention-${kid.student_id}`}
          type="range"
          min={0}
          max={2}
          step={1}
          value={RETENTION_OPTIONS.findIndex((o) => o.value === retention)}
          disabled={isSaving}
          onChange={(e) => {
            const idx = Number(e.target.value);
            const next = RETENTION_OPTIONS[idx]?.value ?? 90;
            setRetention(next);
            update({ kid_id: kid.student_id, retention_days: next });
          }}
          style={{ display: 'block', marginTop: 6, width: 220 }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', width: 220, fontSize: 11, color: '#6b7280' }}>
          {RETENTION_OPTIONS.map((o) => (
            <span key={o.value}>{o.label}</span>
          ))}
        </div>
        <p style={{ ...helpStyle, marginTop: 6 }}>
          Currently:{' '}
          <strong>
            {RETENTION_OPTIONS.find((o) => o.value === retention)?.label ?? `${retention} days`}
          </strong>
        </p>
      </div>

      {/* Push time pickers */}
      <div style={{ marginTop: 14, display: 'flex', gap: 18, flexWrap: 'wrap' }}>
        <div>
          <label htmlFor={`dci-kid-time-${kid.student_id}`} style={labelStyle}>
            Kid reminder time
          </label>
          <p style={helpStyle}>Default 3:15 PM. Saved when you click Save.</p>
          <input
            id={`dci-kid-time-${kid.student_id}`}
            type="time"
            value={kidTime}
            disabled={isSaving}
            onChange={(e) => setKidTime(e.target.value)}
            onBlur={() => {
              if (kidTime && kidTime !== consent.kid_push_time) {
                update({ kid_id: kid.student_id, kid_push_time: kidTime });
              }
            }}
            style={{ display: 'block', marginTop: 6, padding: '6px 8px', borderRadius: 6, border: '1px solid #cbd5e1' }}
          />
        </div>
        <div>
          <label htmlFor={`dci-parent-time-${kid.student_id}`} style={labelStyle}>
            Parent digest time
          </label>
          <p style={helpStyle}>Default 7:00 PM. Saved when you click Save.</p>
          <input
            id={`dci-parent-time-${kid.student_id}`}
            type="time"
            value={parentTime}
            disabled={isSaving}
            onChange={(e) => setParentTime(e.target.value)}
            onBlur={() => {
              if (parentTime && parentTime !== consent.parent_push_time) {
                update({ kid_id: kid.student_id, parent_push_time: parentTime });
              }
            }}
            style={{ display: 'block', marginTop: 6, padding: '6px 8px', borderRadius: 6, border: '1px solid #cbd5e1' }}
          />
        </div>
      </div>

      {upsert.isError && (
        <p role="alert" style={{ color: '#b91c1c', marginTop: 8, fontSize: 12 }}>
          Couldn't save. Please try again.
        </p>
      )}
    </div>
  );
}

export interface DciSettingsSectionProps {
  /** Skip the children fetch (e.g., already have them). */
  kids?: ChildSummary[];
}

/**
 * Daily Check-In settings block for /settings/account.
 *
 * Renders one card per linked kid with DCI toggle, mute, retention,
 * and push-time pickers. Each control persists via POST /api/dci/consent.
 */
export function DciSettingsSection({ kids: kidsOverride }: DciSettingsSectionProps = {}) {
  const childrenQuery = useQuery<ChildSummary[]>({
    queryKey: ['dciConsent', 'kidsForSettings'],
    queryFn: parentApi.getChildren,
    enabled: !kidsOverride,
  });
  const kids = kidsOverride ?? childrenQuery.data ?? [];
  const consentQuery = useDciConsentList(kids.length > 0);

  const consentByKidId = useMemo(() => {
    const map = new Map<number, DciConsent>();
    for (const c of consentQuery.data ?? []) map.set(c.kid_id, c);
    return map;
  }, [consentQuery.data]);

  const isLoading =
    (!kidsOverride && childrenQuery.isLoading) || consentQuery.isLoading;

  return (
    <section
      className="account-section"
      style={sectionStyle}
      data-testid="dci-settings-section"
    >
      <h2>Daily Check-In</h2>
      <p style={{ color: '#6b7280', marginBottom: 12, fontSize: 14 }}>
        Control your child's 60-second daily check-in: who can do it,
        what gets shared, how long we keep it, and when reminders go out.
      </p>

      {isLoading && <p className="account-loading">Loading…</p>}

      {!isLoading && kids.length === 0 && (
        <p style={helpStyle}>
          Link a child first, then come back to set Daily Check-In preferences.
        </p>
      )}

      {!isLoading &&
        kids.map((kid) => {
          const consent = consentByKidId.get(kid.student_id);
          if (!consent) return null;
          // Compose a key from the consent snapshot so the row remounts
          // (and the local edit-buffer reinitialises) whenever the upstream
          // snapshot changes — avoids setState-in-effect.
          const k = [
            kid.student_id,
            consent.retention_days,
            consent.kid_push_time,
            consent.parent_push_time,
          ].join(':');
          return <KidConsentRow key={k} kid={kid} consent={consent} />;
        })}
    </section>
  );
}

export default DciSettingsSection;
