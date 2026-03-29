/**
 * Client-side rate limiting for journey hints (#2609).
 *
 * - Max 1 hint per browser session (sessionStorage)
 * - Max 1 hint per calendar day (localStorage)
 */

const SESSION_KEY = "journey_hint_session_count";
const DAILY_KEY = "journey_hint_daily";

/** Returns true if a hint can be shown in the current browser session. */
export function canShowHintThisSession(): boolean {
  const count = parseInt(sessionStorage.getItem(SESSION_KEY) || "0", 10);
  return count < 1;
}

/** Record that a hint was shown this session. */
export function recordHintShown(): void {
  const count = parseInt(sessionStorage.getItem(SESSION_KEY) || "0", 10);
  sessionStorage.setItem(SESSION_KEY, String(count + 1));
  // Also record daily cap
  localStorage.setItem(DAILY_KEY, new Date().toISOString().slice(0, 10));
}

/** Returns true if no hint has been shown today (based on local date). */
export function canShowHintToday(): boolean {
  const lastDate = localStorage.getItem(DAILY_KEY);
  return lastDate !== new Date().toISOString().slice(0, 10);
}
