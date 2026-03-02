import React, { useState, useEffect } from 'react';
import { webPushService } from '../services/pushNotifications';
import './PushNotificationSetup.css';

const DISMISSED_KEY = 'push_notification_banner_dismissed';
const ENABLED_KEY = 'push_notifications_enabled';

type BannerState = 'idle' | 'requesting' | 'enabled' | 'denied' | 'dismissed';

/**
 * PushNotificationSetup — a non-intrusive banner prompting the user to
 * enable browser push notifications.
 *
 * Behaviour:
 * - Hidden if the user has previously dismissed the banner (localStorage).
 * - Hidden if push is already enabled (localStorage flag).
 * - Hidden if the browser does not support Notification API.
 * - On "Enable": requests permission, initialises Firebase, registers token.
 * - On "Dismiss": sets localStorage flag so the banner never shows again.
 *
 * This component must NOT be placed inside DashboardLayout.tsx directly —
 * the merge agent will handle wiring it into the layout.
 */
export default function PushNotificationSetup(): React.ReactElement | null {
  const [state, setState] = useState<BannerState>('idle');
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // Only show when:
    //  1. Browser supports Notification API
    //  2. User has not dismissed the banner before
    //  3. Push is not already enabled
    //  4. Notification permission is not already denied
    const isSupported = 'Notification' in window && 'serviceWorker' in navigator;
    const isDismissed = localStorage.getItem(DISMISSED_KEY) === 'true';
    const isAlreadyEnabled = localStorage.getItem(ENABLED_KEY) === 'true';
    const isDenied = isSupported && Notification.permission === 'denied';

    if (isSupported && !isDismissed && !isAlreadyEnabled && !isDenied) {
      setVisible(true);
    }
  }, []);

  async function handleEnable() {
    setState('requesting');
    try {
      const success = await webPushService.initialize();
      if (success) {
        localStorage.setItem(ENABLED_KEY, 'true');
        setState('enabled');
        // Auto-hide the success message after 3 seconds
        setTimeout(() => setVisible(false), 3000);
      } else {
        // Permission denied or Firebase not configured
        setState('denied');
      }
    } catch {
      setState('denied');
    }
  }

  function handleDismiss() {
    localStorage.setItem(DISMISSED_KEY, 'true');
    setState('dismissed');
    setVisible(false);
  }

  if (!visible || state === 'dismissed') {
    return null;
  }

  return (
    <div className="push-setup-banner" role="banner" aria-live="polite">
      <div className="push-setup-banner__icon" aria-hidden="true">
        {state === 'enabled' ? '✓' : '🔔'}
      </div>

      <div className="push-setup-banner__content">
        {state === 'idle' && (
          <>
            <span className="push-setup-banner__text">
              Enable push notifications to get real-time alerts for assignments,
              messages, and reminders.
            </span>
            <div className="push-setup-banner__actions">
              <button
                className="push-setup-banner__btn push-setup-banner__btn--primary"
                onClick={handleEnable}
              >
                Enable
              </button>
              <button
                className="push-setup-banner__btn push-setup-banner__btn--secondary"
                onClick={handleDismiss}
              >
                Dismiss
              </button>
            </div>
          </>
        )}

        {state === 'requesting' && (
          <span className="push-setup-banner__text">
            Enabling push notifications...
          </span>
        )}

        {state === 'enabled' && (
          <span className="push-setup-banner__text push-setup-banner__text--success">
            Push notifications enabled
          </span>
        )}

        {state === 'denied' && (
          <>
            <span className="push-setup-banner__text push-setup-banner__text--warning">
              Push notifications blocked. You can enable them in your browser
              settings.
            </span>
            <div className="push-setup-banner__actions">
              <button
                className="push-setup-banner__btn push-setup-banner__btn--secondary"
                onClick={handleDismiss}
              >
                Dismiss
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
