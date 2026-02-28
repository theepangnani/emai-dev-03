import { useState, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import './CookieConsentBanner.css';

const CONSENT_KEY = 'cookie_consent';

interface ConsentChoices {
  essential: boolean;
  analytics: boolean;
  ai_processing: boolean;
}

const DEFAULT_CHOICES: ConsentChoices = {
  essential: true,
  analytics: false,
  ai_processing: false,
};

/** All localStorage / cookie items used by ClassBridge. */
const STORAGE_INVENTORY = [
  { name: 'token', category: 'Essential', purpose: 'Authentication JWT' },
  { name: 'refresh_token', category: 'Essential', purpose: 'Token refresh for session continuity' },
  { name: 'last_selected_child', category: 'Essential', purpose: 'Remember selected child (parent UX)' },
  { name: 'view_mode', category: 'Essential', purpose: 'Dashboard view mode preference' },
  { name: 'streak_milestone_*_dismissed', category: 'Essential', purpose: 'Streak milestone dismiss state' },
  { name: 'cookie_consent', category: 'Essential', purpose: 'Stores your consent choices' },
  { name: 'pd-section-states', category: 'Essential', purpose: 'Dashboard section collapse states' },
  { name: 'pd-view-mode', category: 'Essential', purpose: 'Parent dashboard view mode' },
  { name: 'chunk_reload', category: 'Essential', purpose: 'Handles deploy-time cache refresh' },
  { name: 'theme', category: 'Essential', purpose: 'Light/dark theme preference' },
];

function loadStoredConsent(): ConsentChoices | null {
  try {
    const raw = localStorage.getItem(CONSENT_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return null;
}

function saveConsent(choices: ConsentChoices) {
  localStorage.setItem(CONSENT_KEY, JSON.stringify(choices));
}

export function CookieConsentBanner() {
  const { user } = useAuth();
  const [visible, setVisible] = useState(() => !loadStoredConsent());
  const [showPrefs, setShowPrefs] = useState(false);
  const [choices, setChoices] = useState<ConsentChoices>(() => loadStoredConsent() || DEFAULT_CHOICES);

  const persistToBackend = useCallback(async (prefs: ConsentChoices) => {
    // Only send to backend if user is logged in
    if (!user) return;
    try {
      await api.put('/api/users/me/consent-preferences', {
        essential: true,
        analytics: prefs.analytics,
        ai_processing: prefs.ai_processing,
      });
    } catch {
      // Best-effort — don't block UX if backend call fails
    }
  }, [user]);

  const handleAcceptAll = useCallback(() => {
    const allOn: ConsentChoices = { essential: true, analytics: true, ai_processing: true };
    setChoices(allOn);
    saveConsent(allOn);
    setVisible(false);
    setShowPrefs(false);
    persistToBackend(allOn);
  }, [persistToBackend]);

  const handleSavePreferences = useCallback(() => {
    const finalChoices = { ...choices, essential: true }; // Essential always on
    setChoices(finalChoices);
    saveConsent(finalChoices);
    setVisible(false);
    setShowPrefs(false);
    persistToBackend(finalChoices);
  }, [choices, persistToBackend]);

  if (!visible) return null;

  return (
    <>
      {/* Main banner */}
      {!showPrefs && (
        <div className="cookie-banner" role="region" aria-label="Cookie consent">
          <div className="cookie-banner__text">
            <h3>We value your privacy</h3>
            <p>
              ClassBridge uses essential cookies and localStorage to keep you signed in and
              remember your preferences. Optional cookies help us improve the platform.{' '}
              <a href="/privacy" target="_blank" rel="noopener noreferrer">Privacy Policy</a>
            </p>
          </div>
          <div className="cookie-banner__actions">
            <button
              className="cookie-banner__btn cookie-banner__btn--manage"
              onClick={() => setShowPrefs(true)}
            >
              Manage Preferences
            </button>
            <button
              className="cookie-banner__btn cookie-banner__btn--accept"
              onClick={handleAcceptAll}
            >
              Accept All
            </button>
          </div>
        </div>
      )}

      {/* Preferences modal */}
      {showPrefs && (
        <div className="cookie-prefs-overlay" onClick={() => setShowPrefs(false)}>
          <div
            className="cookie-prefs-modal"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-label="Cookie preferences"
          >
            <h2>Cookie Preferences</h2>
            <p>
              Choose which categories of cookies and local data storage you allow.
              Essential items are always active because they are required for the
              platform to function.
            </p>

            {/* Essential */}
            <div className="cookie-prefs-category">
              <div className="cookie-prefs-category__header">
                <div className="cookie-prefs-category__info">
                  <h4>Essential <span className="cookie-prefs-tag">Always on</span></h4>
                  <p>
                    Required for authentication, navigation, and core functionality.
                    These cannot be disabled.
                  </p>
                </div>
                <label className="cookie-toggle">
                  <input type="checkbox" checked disabled />
                  <span className="cookie-toggle__slider" />
                </label>
              </div>
            </div>

            {/* Analytics */}
            <div className="cookie-prefs-category">
              <div className="cookie-prefs-category__header">
                <div className="cookie-prefs-category__info">
                  <h4>Analytics</h4>
                  <p>
                    Help us understand how ClassBridge is used so we can improve the
                    experience. No personal data is shared with third parties.
                  </p>
                </div>
                <label className="cookie-toggle">
                  <input
                    type="checkbox"
                    checked={choices.analytics}
                    onChange={(e) => setChoices({ ...choices, analytics: e.target.checked })}
                  />
                  <span className="cookie-toggle__slider" />
                </label>
              </div>
            </div>

            {/* AI Processing */}
            <div className="cookie-prefs-category">
              <div className="cookie-prefs-category__header">
                <div className="cookie-prefs-category__info">
                  <h4>AI Processing</h4>
                  <p>
                    Enables AI-powered features like study guide generation, quiz
                    creation, and personalized learning recommendations.
                  </p>
                </div>
                <label className="cookie-toggle">
                  <input
                    type="checkbox"
                    checked={choices.ai_processing}
                    onChange={(e) => setChoices({ ...choices, ai_processing: e.target.checked })}
                  />
                  <span className="cookie-toggle__slider" />
                </label>
              </div>
            </div>

            {/* Storage inventory */}
            <div className="cookie-inventory">
              <details>
                <summary>View all stored items</summary>
                <table>
                  <thead>
                    <tr>
                      <th>Item</th>
                      <th>Category</th>
                      <th>Purpose</th>
                    </tr>
                  </thead>
                  <tbody>
                    {STORAGE_INVENTORY.map((item) => (
                      <tr key={item.name}>
                        <td><code>{item.name}</code></td>
                        <td>{item.category}</td>
                        <td>{item.purpose}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>
            </div>

            <div className="cookie-prefs-modal__actions">
              <button
                className="cookie-banner__btn cookie-banner__btn--manage"
                onClick={() => setShowPrefs(false)}
              >
                Cancel
              </button>
              <button
                className="cookie-banner__btn cookie-banner__btn--accept"
                onClick={handleSavePreferences}
              >
                Save Preferences
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
