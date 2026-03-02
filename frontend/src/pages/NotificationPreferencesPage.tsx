/**
 * Notification Preferences page (#966).
 * Allows users to configure per-type in-app/email toggles and daily digest settings.
 */
import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { DashboardLayout } from '../components/DashboardLayout';
import { notificationsApi } from '../api/notifications';
import type { AdvancedNotificationPreferences, AdvancedNotificationPreferencesResponse } from '../api/notifications';
import { useToast } from '../components/Toast';
import './NotificationPreferencesPage.css';

// Digest hour options: 6am through 10pm (18:00 = 6pm, 22:00 = 10pm)
const DIGEST_HOUR_OPTIONS: { value: number; label: string }[] = [
  { value: 6, label: '6:00 AM' },
  { value: 7, label: '7:00 AM' },
  { value: 8, label: '8:00 AM' },
  { value: 9, label: '9:00 AM' },
  { value: 10, label: '10:00 AM' },
  { value: 11, label: '11:00 AM' },
  { value: 12, label: '12:00 PM (Noon)' },
  { value: 13, label: '1:00 PM' },
  { value: 14, label: '2:00 PM' },
  { value: 15, label: '3:00 PM' },
  { value: 16, label: '4:00 PM' },
  { value: 17, label: '5:00 PM' },
  { value: 18, label: '6:00 PM' },
  { value: 19, label: '7:00 PM' },
  { value: 20, label: '8:00 PM' },
  { value: 21, label: '9:00 PM' },
  { value: 22, label: '10:00 PM' },
];

interface ToggleRowProps {
  label: string;
  description?: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
}

function ToggleRow({ label, description, checked, onChange, disabled = false }: ToggleRowProps) {
  return (
    <div className={`pref-toggle-row ${disabled ? 'pref-toggle-row--disabled' : ''}`}>
      <div className="pref-toggle-info">
        <span className="pref-toggle-label">{label}</span>
        {description && <span className="pref-toggle-desc">{description}</span>}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        className={`pref-toggle-switch ${checked ? 'pref-toggle-switch--on' : ''}`}
        onClick={() => !disabled && onChange(!checked)}
        aria-label={`Toggle ${label}`}
      >
        <span className="pref-toggle-knob" />
      </button>
    </div>
  );
}

const DEFAULT_PREFS: AdvancedNotificationPreferences = {
  in_app_assignments: true,
  in_app_messages: true,
  in_app_tasks: true,
  in_app_system: true,
  in_app_reminders: true,
  email_assignments: true,
  email_messages: true,
  email_tasks: true,
  email_reminders: true,
  digest_mode: false,
  digest_hour: 8,
};

export function NotificationPreferencesPage() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: serverPrefs, isLoading } = useQuery<AdvancedNotificationPreferencesResponse>({
    queryKey: ['notificationPreferences'],
    queryFn: notificationsApi.getPreferences,
  });

  const [prefs, setPrefs] = useState<AdvancedNotificationPreferences>(DEFAULT_PREFS);
  const [dirty, setDirty] = useState(false);

  // Populate local state once server data arrives
  useEffect(() => {
    if (serverPrefs) {
      setPrefs({
        in_app_assignments: serverPrefs.in_app_assignments,
        in_app_messages: serverPrefs.in_app_messages,
        in_app_tasks: serverPrefs.in_app_tasks,
        in_app_system: serverPrefs.in_app_system,
        in_app_reminders: serverPrefs.in_app_reminders,
        email_assignments: serverPrefs.email_assignments,
        email_messages: serverPrefs.email_messages,
        email_tasks: serverPrefs.email_tasks,
        email_reminders: serverPrefs.email_reminders,
        digest_mode: serverPrefs.digest_mode,
        digest_hour: serverPrefs.digest_hour,
      });
      setDirty(false);
    }
  }, [serverPrefs]);

  const saveMutation = useMutation({
    mutationFn: (data: AdvancedNotificationPreferences) => notificationsApi.updatePreferences(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notificationPreferences'] });
      setDirty(false);
      toast('Notification preferences saved.', 'success');
    },
    onError: () => {
      toast('Failed to save preferences. Please try again.', 'error');
    },
  });

  function update<K extends keyof AdvancedNotificationPreferences>(
    key: K,
    value: AdvancedNotificationPreferences[K],
  ) {
    setPrefs(prev => ({ ...prev, [key]: value }));
    setDirty(true);
  }

  function handleSave(e: React.FormEvent) {
    e.preventDefault();
    saveMutation.mutate(prefs);
  }

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="np-page">
          <div className="np-loading">Loading preferences...</div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="np-page">
        <div className="np-header">
          <h1 className="np-title">Notification Preferences</h1>
          <p className="np-subtitle">
            Control which notifications you receive in-app and by email.
          </p>
        </div>

        <form className="np-form" onSubmit={handleSave}>
          {/* ── In-App Notifications ─────────────────────────────── */}
          <section className="np-section">
            <h2 className="np-section-title">In-App Notifications</h2>
            <p className="np-section-desc">
              These notifications appear in the notification bell inside ClassBridge.
            </p>
            <div className="np-toggle-list">
              <ToggleRow
                label="Assignments"
                description="Due date reminders and grade notifications"
                checked={prefs.in_app_assignments}
                onChange={v => update('in_app_assignments', v)}
              />
              <ToggleRow
                label="Messages"
                description="New messages from teachers and parents"
                checked={prefs.in_app_messages}
                onChange={v => update('in_app_messages', v)}
              />
              <ToggleRow
                label="Tasks"
                description="Task due date reminders"
                checked={prefs.in_app_tasks}
                onChange={v => update('in_app_tasks', v)}
              />
              <ToggleRow
                label="Reminders"
                description="Study reminders and upcoming events"
                checked={prefs.in_app_reminders}
                onChange={v => update('in_app_reminders', v)}
              />
              <ToggleRow
                label="System"
                description="Account updates, link requests, and platform notices"
                checked={prefs.in_app_system}
                onChange={v => update('in_app_system', v)}
              />
            </div>
          </section>

          {/* ── Email Notifications ──────────────────────────────── */}
          <section className="np-section">
            <h2 className="np-section-title">Email Notifications</h2>
            <p className="np-section-desc">
              Control which events trigger an email to you. When digest mode is on,
              these emails are batched into a single daily summary instead.
            </p>
            <div className="np-toggle-list">
              <ToggleRow
                label="Assignments"
                description="Due date reminders and grade posted emails"
                checked={prefs.email_assignments}
                onChange={v => update('email_assignments', v)}
              />
              <ToggleRow
                label="Messages"
                description="Email alert when you receive a new message"
                checked={prefs.email_messages}
                onChange={v => update('email_messages', v)}
              />
              <ToggleRow
                label="Tasks"
                description="Task due date reminder emails"
                checked={prefs.email_tasks}
                onChange={v => update('email_tasks', v)}
              />
              <ToggleRow
                label="Reminders"
                description="Scheduled reminder emails"
                checked={prefs.email_reminders}
                onChange={v => update('email_reminders', v)}
              />
            </div>
          </section>

          {/* ── Email Digest ─────────────────────────────────────── */}
          <section className="np-section">
            <h2 className="np-section-title">Email Digest</h2>
            <p className="np-section-desc">
              Instead of receiving individual emails immediately, get all your
              notifications bundled into a single daily digest email.
            </p>
            <div className="np-toggle-list">
              <ToggleRow
                label="Daily digest mode"
                description="Send one summary email per day instead of immediate emails"
                checked={prefs.digest_mode}
                onChange={v => update('digest_mode', v)}
              />
            </div>

            {prefs.digest_mode && (
              <div className="np-digest-hour">
                <label htmlFor="digest-hour" className="np-digest-hour-label">
                  Send digest at
                </label>
                <select
                  id="digest-hour"
                  className="np-digest-hour-select"
                  value={prefs.digest_hour}
                  onChange={e => update('digest_hour', Number(e.target.value))}
                >
                  {DIGEST_HOUR_OPTIONS.map(opt => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
                <span className="np-digest-hour-note">(UTC time)</span>
              </div>
            )}
          </section>

          {/* ── Save Button ──────────────────────────────────────── */}
          <div className="np-footer">
            <button
              type="submit"
              className="np-save-btn"
              disabled={saveMutation.isPending || !dirty}
            >
              {saveMutation.isPending ? 'Saving...' : 'Save Preferences'}
            </button>
            {!dirty && !saveMutation.isPending && (
              <span className="np-saved-note">All changes saved</span>
            )}
          </div>
        </form>
      </div>
    </DashboardLayout>
  );
}
