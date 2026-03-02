import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { DashboardLayout } from '../components/DashboardLayout';
import { useAuth } from '../context/AuthContext';
import { smartRemindersApi, type ReminderPreferences, type ReminderLog, type ReminderUrgency } from '../api/smartReminders';
import './ReminderPreferencesPage.css';

const ESCALATION_OPTIONS = [
  { label: '12 hours', value: 12 },
  { label: '24 hours', value: 24 },
  { label: '48 hours', value: 48 },
  { label: 'Never', value: 0 },
];

const URGENCY_LABELS: Record<ReminderUrgency, { label: string; color: string }> = {
  low:      { label: 'Low (3+ days out)',   color: '#38a169' },
  medium:   { label: 'Medium (1 day out)',  color: '#d69e2e' },
  high:     { label: 'High (3 hours out)',  color: '#e53e3e' },
  critical: { label: 'Critical (past due)', color: '#702459' },
};

function UrgencyBadge({ urgency }: { urgency: ReminderUrgency }) {
  const info = URGENCY_LABELS[urgency] || { label: urgency, color: '#718096' };
  return (
    <span className="urgency-badge" style={{ background: info.color }}>
      {info.label.split(' ')[0]}
    </span>
  );
}

function ToggleSwitch({ checked, onChange, disabled }: { checked: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
  return (
    <label className="toggle-switch">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        disabled={disabled}
      />
      <span className="toggle-track">
        <span className="toggle-thumb" />
      </span>
    </label>
  );
}

export function ReminderPreferencesPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const queryClient = useQueryClient();

  const [successMsg, setSuccessMsg] = useState('');
  const [triggerResult, setTriggerResult] = useState<string>('');
  const [triggerLoading, setTriggerLoading] = useState(false);

  const { data: prefs, isLoading: prefsLoading } = useQuery<ReminderPreferences>({
    queryKey: ['reminder-preferences'],
    queryFn: () => smartRemindersApi.getPreferences(),
  });

  const { data: logs = [], isLoading: logsLoading } = useQuery<ReminderLog[]>({
    queryKey: ['reminder-logs'],
    queryFn: () => smartRemindersApi.getLogs(10),
  });

  const updateMutation = useMutation({
    mutationFn: smartRemindersApi.updatePreferences,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reminder-preferences'] });
      setSuccessMsg('Preferences saved.');
      setTimeout(() => setSuccessMsg(''), 3000);
    },
  });

  // Local copy for optimistic UI
  const [local, setLocal] = useState<ReminderPreferences | null>(null);

  useEffect(() => {
    if (prefs && !local) {
      setLocal(prefs);
    }
  }, [prefs, local]);

  function handleToggle(field: keyof ReminderPreferences, value: boolean) {
    if (!local) return;
    const updated = { ...local, [field]: value };
    setLocal(updated);
    updateMutation.mutate({ [field]: value });
  }

  function handleEscalationChange(e: React.ChangeEvent<HTMLSelectElement>) {
    if (!local) return;
    const hours = Number(e.target.value);
    const updated = { ...local, parent_escalation_hours: hours };
    setLocal(updated);
    updateMutation.mutate({ parent_escalation_hours: hours });
  }

  async function handleTrigger() {
    setTriggerLoading(true);
    setTriggerResult('');
    try {
      const result = await smartRemindersApi.triggerRun();
      setTriggerResult(result.message);
    } catch {
      setTriggerResult('Failed to trigger reminder run. Check server logs.');
    } finally {
      setTriggerLoading(false);
      queryClient.invalidateQueries({ queryKey: ['reminder-logs'] });
    }
  }

  const displayPrefs = local ?? prefs;

  return (
    <DashboardLayout welcomeSubtitle="Manage how and when you receive assignment reminders">
      <div className="reminder-prefs-page">
        <h1 className="reminder-prefs-title">Reminder Settings</h1>
        <p className="reminder-prefs-subtitle">
          Control when you get notified about upcoming and overdue assignments.
        </p>

        {prefsLoading && <div className="reminder-prefs-loading">Loading preferences...</div>}
        {successMsg && <div className="reminder-prefs-success">{successMsg}</div>}

        {displayPrefs && (
          <>
            {/* Timing toggles */}
            <section className="reminder-prefs-section">
              <h2 className="reminder-prefs-section-title">Reminder Timing</h2>
              <div className="reminder-prefs-row">
                <div className="reminder-prefs-row-info">
                  <span className="reminder-prefs-row-label">3 Days Before Due</span>
                  <span className="reminder-prefs-row-desc">Get an early heads-up while there is still time to plan.</span>
                </div>
                <ToggleSwitch
                  checked={displayPrefs.remind_3_days}
                  onChange={(v) => handleToggle('remind_3_days', v)}
                />
              </div>
              <div className="reminder-prefs-row">
                <div className="reminder-prefs-row-info">
                  <span className="reminder-prefs-row-label">1 Day Before Due</span>
                  <span className="reminder-prefs-row-desc">A reminder the day before the deadline.</span>
                </div>
                <ToggleSwitch
                  checked={displayPrefs.remind_1_day}
                  onChange={(v) => handleToggle('remind_1_day', v)}
                />
              </div>
              <div className="reminder-prefs-row">
                <div className="reminder-prefs-row-info">
                  <span className="reminder-prefs-row-label">3 Hours Before Due</span>
                  <span className="reminder-prefs-row-desc">Last-chance alert when the deadline is near.</span>
                </div>
                <ToggleSwitch
                  checked={displayPrefs.remind_3_hours}
                  onChange={(v) => handleToggle('remind_3_hours', v)}
                />
              </div>
              <div className="reminder-prefs-row">
                <div className="reminder-prefs-row-info">
                  <span className="reminder-prefs-row-label">Overdue Alerts</span>
                  <span className="reminder-prefs-row-desc">Notify when an assignment is past its due date.</span>
                </div>
                <ToggleSwitch
                  checked={displayPrefs.remind_overdue}
                  onChange={(v) => handleToggle('remind_overdue', v)}
                />
              </div>
            </section>

            {/* AI personalization */}
            <section className="reminder-prefs-section">
              <h2 className="reminder-prefs-section-title">AI Personalized Messages</h2>
              <div className="reminder-prefs-row">
                <div className="reminder-prefs-row-info">
                  <span className="reminder-prefs-row-label">AI-Written Reminders</span>
                  <span className="reminder-prefs-row-desc">
                    Let ClassBridge AI craft short, personalized reminder messages based on your assignment context.
                    When off, generic template messages are used.
                  </span>
                </div>
                <ToggleSwitch
                  checked={displayPrefs.ai_personalized_messages}
                  onChange={(v) => handleToggle('ai_personalized_messages', v)}
                />
              </div>
            </section>

            {/* Parent escalation (shown for students/parents) */}
            {(user?.role === 'student' || user?.role === 'parent') && (
              <section className="reminder-prefs-section">
                <h2 className="reminder-prefs-section-title">Parent Escalation</h2>
                <div className="reminder-prefs-row">
                  <div className="reminder-prefs-row-info">
                    <span className="reminder-prefs-row-label">Notify Parent After Overdue</span>
                    <span className="reminder-prefs-row-desc">
                      If an assignment stays overdue for this long, linked parents are automatically notified.
                      Select "Never" to disable parent escalation.
                    </span>
                  </div>
                  <select
                    className="reminder-escalation-select"
                    value={displayPrefs.parent_escalation_hours}
                    onChange={handleEscalationChange}
                  >
                    {ESCALATION_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                </div>
              </section>
            )}

            {/* Admin trigger */}
            {isAdmin && (
              <section className="reminder-prefs-section">
                <h2 className="reminder-prefs-section-title">Admin Controls</h2>
                <div className="reminder-admin-controls">
                  <button
                    className="reminder-trigger-btn"
                    onClick={handleTrigger}
                    disabled={triggerLoading}
                  >
                    {triggerLoading ? 'Running...' : 'Trigger Reminder Run Now'}
                  </button>
                  {triggerResult && (
                    <p className="reminder-trigger-result">{triggerResult}</p>
                  )}
                </div>
              </section>
            )}
          </>
        )}

        {/* Recent reminder log */}
        <section className="reminder-prefs-section">
          <h2 className="reminder-prefs-section-title">Recent Reminders</h2>
          {logsLoading && <p className="reminder-log-loading">Loading logs...</p>}
          {!logsLoading && logs.length === 0 && (
            <p className="reminder-log-empty">No reminders sent yet.</p>
          )}
          {logs.length > 0 && (
            <ul className="reminder-log-list">
              {logs.map((log) => (
                <li key={log.id} className="reminder-log-item">
                  <div className="reminder-log-meta">
                    <UrgencyBadge urgency={log.urgency} />
                    <span className="reminder-log-channel">{log.channel}</span>
                    {log.priority_score != null && (
                      <span className="reminder-log-score">score: {log.priority_score}</span>
                    )}
                    <span className="reminder-log-time">
                      {new Date(log.sent_at).toLocaleString()}
                    </span>
                  </div>
                  <p className="reminder-log-message">{log.message}</p>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </DashboardLayout>
  );
}

export default ReminderPreferencesPage;
