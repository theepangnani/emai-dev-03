/**
 * WebPushService — Firebase Cloud Messaging for the web frontend.
 *
 * Usage:
 *   import { webPushService } from './services/pushNotifications';
 *   await webPushService.initialize();
 *
 * Required npm packages (install once):
 *   npm install firebase
 *
 * Required environment variables (set in .env.local or .env.production):
 *   VITE_FIREBASE_API_KEY
 *   VITE_FIREBASE_AUTH_DOMAIN
 *   VITE_FIREBASE_PROJECT_ID
 *   VITE_FIREBASE_MESSAGING_SENDER_ID
 *   VITE_FIREBASE_APP_ID
 *   VITE_FIREBASE_VAPID_KEY
 */

import { pushApi } from '../api/pushNotifications';

const VAPID_PUBLIC_KEY = import.meta.env.VITE_FIREBASE_VAPID_KEY as string | undefined;

const FIREBASE_CONFIG = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY as string | undefined,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN as string | undefined,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID as string | undefined,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID as string | undefined,
  appId: import.meta.env.VITE_FIREBASE_APP_ID as string | undefined,
};

function isFirebaseConfigured(): boolean {
  return !!(
    FIREBASE_CONFIG.apiKey &&
    FIREBASE_CONFIG.projectId &&
    FIREBASE_CONFIG.messagingSenderId &&
    FIREBASE_CONFIG.appId &&
    VAPID_PUBLIC_KEY
  );
}

export class WebPushService {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private messaging: any = null;
  private currentToken: string | null = null;

  /**
   * Initialize Firebase Messaging and register the FCM token with the backend.
   *
   * Steps:
   *  1. Check browser support and Notification permission.
   *  2. Dynamically import the Firebase SDK.
   *  3. Initialize the Firebase app (idempotent — reuses existing app).
   *  4. Obtain an FCM web token using the VAPID key.
   *  5. POST the token to /api/push/register.
   *
   * Returns true when a token was successfully registered, false otherwise.
   */
  async initialize(): Promise<boolean> {
    if (!isFirebaseConfigured()) {
      console.debug(
        '[WebPush] Firebase env vars not set — push notifications disabled.'
      );
      return false;
    }

    if (!('Notification' in window)) {
      console.debug('[WebPush] Browser does not support notifications.');
      return false;
    }

    if (!('serviceWorker' in navigator)) {
      console.debug('[WebPush] Service workers not supported.');
      return false;
    }

    const granted = await this.requestPermission();
    if (!granted) {
      return false;
    }

    try {
      const token = await this.getToken();
      if (!token) {
        return false;
      }
      this.currentToken = token;

      // Register with backend
      await pushApi.register({
        token,
        platform: 'web',
        device_name: _getDeviceName(),
        app_version: _getAppVersion(),
      });

      console.info('[WebPush] Push notifications registered successfully.');
      return true;
    } catch (err) {
      console.warn('[WebPush] Failed to initialize push notifications:', err);
      return false;
    }
  }

  /**
   * Request the browser Notification permission.
   * Returns true when the user grants permission.
   */
  async requestPermission(): Promise<boolean> {
    const current = Notification.permission;
    if (current === 'granted') return true;
    if (current === 'denied') return false;

    const result = await Notification.requestPermission();
    return result === 'granted';
  }

  /**
   * Return the current FCM token for this browser/device.
   * Returns null when Firebase is not configured or permission is denied.
   */
  async getToken(): Promise<string | null> {
    if (!isFirebaseConfigured()) return null;
    if (Notification.permission !== 'granted') return null;

    try {
      const messaging = await this._getMessaging();
      if (!messaging) return null;

      // Dynamic import to avoid bundling Firebase when env vars absent
      const { getToken } = await import('firebase/messaging');
      const token = await getToken(messaging, { vapidKey: VAPID_PUBLIC_KEY });
      return token || null;
    } catch (err) {
      console.warn('[WebPush] getToken failed:', err);
      return null;
    }
  }

  /**
   * Delete the FCM token and notify the backend.
   */
  async unregister(): Promise<void> {
    try {
      const token = this.currentToken || (await this.getToken());
      if (!token) return;

      // Notify FCM
      const messaging = await this._getMessaging();
      if (messaging) {
        const { deleteToken } = await import('firebase/messaging');
        await deleteToken(messaging);
      }

      // Notify backend
      await pushApi.unregister(token);
      this.currentToken = null;
      console.info('[WebPush] Push notifications unregistered.');
    } catch (err) {
      console.warn('[WebPush] unregister failed:', err);
    }
  }

  /**
   * Register a foreground message handler.
   * FCM only delivers messages via this callback when the page is in focus.
   * Background messages are handled by the service worker.
   */
  onMessage(callback: (payload: unknown) => void): void {
    this._getMessaging().then((messaging) => {
      if (!messaging) return;
      import('firebase/messaging').then(({ onMessage }) => {
        onMessage(messaging, callback);
      });
    });
  }

  // ------------------------------------------------------------------
  // Internal helpers
  // ------------------------------------------------------------------

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private async _getMessaging(): Promise<any | null> {
    if (this.messaging) return this.messaging;
    if (!isFirebaseConfigured()) return null;

    try {
      const { initializeApp, getApps, getApp } = await import('firebase/app');
      const { getMessaging } = await import('firebase/messaging');

      const app =
        getApps().length === 0
          ? initializeApp(FIREBASE_CONFIG as object)
          : getApp();

      this.messaging = getMessaging(app);
      return this.messaging;
    } catch (err) {
      console.warn('[WebPush] Failed to initialize Firebase:', err);
      return null;
    }
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function _getDeviceName(): string {
  const ua = navigator.userAgent;
  // Minimal UA sniffing for a human-friendly label — not exhaustive
  if (/iPhone/.test(ua)) return 'iPhone';
  if (/iPad/.test(ua)) return 'iPad';
  if (/Android/.test(ua)) return 'Android browser';
  if (/Chrome/.test(ua)) return 'Chrome browser';
  if (/Safari/.test(ua)) return 'Safari browser';
  if (/Firefox/.test(ua)) return 'Firefox browser';
  return 'Web browser';
}

function _getAppVersion(): string {
  // Vite injects the package.json version via define — fall back gracefully
  return (import.meta.env.VITE_APP_VERSION as string | undefined) ?? '1.0.0';
}

// ---------------------------------------------------------------------------
// Singleton
// ---------------------------------------------------------------------------
export const webPushService = new WebPushService();
