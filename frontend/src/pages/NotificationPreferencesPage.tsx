import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { notificationsApi } from '../api/notifications';
import type { AdvancedNotificationPreferences, ChannelPreference } from '../api/notifications';

const CATEGORIES: { key: keyof AdvancedNotificationPreferences; label: string; description: string }[] = [
  { key: 'assignments', label: 'Assignments', description: 'New assignments, grades, upcoming assessments' },
  { key: 'messages', label: 'Messages', description: 'Direct messages, parent requests, link requests' },
  { key: 'study_guides', label: 'Study Guides', description: 'Study guide creation, material uploads' },
  { key: 'tasks', label: 'Tasks', description: 'Task due dates and reminders' },
  { key: 'system', label: 'System', description: 'System announcements and admin broadcasts' },
  { key: 'parent_email_digest', label: 'Parent Email Digest', description: 'Daily email summaries for parents' },
];

export function NotificationPreferencesPage() {
  const [prefs, setPrefs] = useState<AdvancedNotificationPreferences | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadPreferences();
  }, []);

  const loadPreferences = async () => {
    try {
      setLoading(true);
      const data = await notificationsApi.getAdvancedPreferences();
      setPrefs(data);
    } catch {
      setError('Failed to load notification preferences');
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = useCallback(async (
    category: keyof AdvancedNotificationPreferences,
    channel: keyof ChannelPreference,
  ) => {
    if (!prefs) return;

    const currentValue = prefs[category][channel];
    const newCategoryPrefs = { ...prefs[category], [channel]: !currentValue };

    // Optimistic update
    setPrefs({ ...prefs, [category]: newCategoryPrefs });
    setSaving(category);

    try {
      const updated = await notificationsApi.updateAdvancedPreferences({
        [category]: newCategoryPrefs,
      });
      setPrefs(updated);
    } catch {
      // Revert on failure
      setPrefs(prefs);
      setError('Failed to save preference');
      setTimeout(() => setError(null), 3000);
    } finally {
      setSaving(null);
    }
  }, [prefs]);

  if (loading) {
    return (
      <div className="page-container">
        <div className="loading-spinner">Loading preferences...</div>
      </div>
    );
  }

  if (error && !prefs) {
    return (
      <div className="page-container">
        <div className="error-message">{error}</div>
      </div>
    );
  }

  return (
    <div className="page-container" style={{ maxWidth: 700, margin: '0 auto', padding: '24px 16px' }}>
      <div style={{ marginBottom: 24 }}>
        <Link to="/notifications" style={{ color: '#6366f1', textDecoration: 'none', fontSize: 14 }}>
          &larr; Back to Notifications
        </Link>
      </div>

      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 8 }}>Notification Preferences</h1>
      <p style={{ color: '#6b7280', marginBottom: 24, fontSize: 14 }}>
        Choose which notifications you receive and how they are delivered.
      </p>

      {error && (
        <div style={{
          background: '#fef2f2', border: '1px solid #fecaca', color: '#dc2626',
          padding: '8px 12px', borderRadius: 8, marginBottom: 16, fontSize: 14,
        }}>
          {error}
        </div>
      )}

      <div style={{
        background: 'var(--card-bg, #fff)',
        borderRadius: 12,
        border: '1px solid var(--border-color, #e5e7eb)',
        overflow: 'hidden',
      }}>
        {/* Header row */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 80px 80px',
          padding: '12px 16px',
          borderBottom: '2px solid var(--border-color, #e5e7eb)',
          background: 'var(--hover-bg, #f9fafb)',
          fontWeight: 600,
          fontSize: 13,
          color: '#6b7280',
        }}>
          <span>Category</span>
          <span style={{ textAlign: 'center' }}>In-App</span>
          <span style={{ textAlign: 'center' }}>Email</span>
        </div>

        {/* Category rows */}
        {prefs && CATEGORIES.map(({ key, label, description }) => (
          <div
            key={key}
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 80px 80px',
              padding: '14px 16px',
              borderBottom: '1px solid var(--border-color, #e5e7eb)',
              alignItems: 'center',
              opacity: saving === key ? 0.7 : 1,
              transition: 'opacity 0.15s',
            }}
          >
            <div>
              <div style={{ fontWeight: 600, fontSize: 15, color: 'var(--text-primary, #111)' }}>
                {label}
              </div>
              <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 2 }}>
                {description}
              </div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <ToggleSwitch
                checked={prefs[key].in_app}
                onChange={() => handleToggle(key, 'in_app')}
                disabled={saving !== null}
              />
            </div>
            <div style={{ textAlign: 'center' }}>
              <ToggleSwitch
                checked={prefs[key].email}
                onChange={() => handleToggle(key, 'email')}
                disabled={saving !== null}
              />
            </div>
          </div>
        ))}
      </div>

      <p style={{ color: '#9ca3af', fontSize: 12, marginTop: 16 }}>
        Changes are saved automatically. Disabling in-app notifications will stop new notifications
        from appearing in your notification bell. Disabling email will stop email alerts for that category.
      </p>
    </div>
  );
}

function ToggleSwitch({ checked, onChange, disabled }: {
  checked: boolean;
  onChange: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={onChange}
      disabled={disabled}
      style={{
        position: 'relative',
        display: 'inline-block',
        width: 44,
        height: 24,
        borderRadius: 12,
        border: 'none',
        cursor: disabled ? 'not-allowed' : 'pointer',
        background: checked ? '#6366f1' : '#d1d5db',
        transition: 'background 0.2s',
        padding: 0,
        opacity: disabled ? 0.5 : 1,
      }}
    >
      <span
        style={{
          position: 'absolute',
          top: 2,
          left: checked ? 22 : 2,
          width: 20,
          height: 20,
          borderRadius: '50%',
          background: '#fff',
          boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
          transition: 'left 0.2s',
        }}
      />
    </button>
  );
}
