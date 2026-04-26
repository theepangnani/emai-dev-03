/**
 * Lightweight client-side telemetry for the kid /checkin flow.
 *
 * Backend telemetry collection is out of scope for M0-9. This emits a
 * `CustomEvent` on `window` so a future shipper can attach a sink without
 * coupling these page files to any analytics SDK. In dev / tests, console
 * output is gated by the `dci.debugTelemetry` localStorage flag so we
 * don't fill up CI logs.
 *
 * Event names follow the design lock § 7 telemetry list:
 *   dci.kid.opened
 *   dci.kid.input_chosen      { type }
 *   dci.kid.classify_ms       { ms }
 *   dci.kid.corrected         { from, to }
 *   dci.kid.completed_seconds { seconds }
 */

export type DciKidEventName =
  | 'dci.kid.opened'
  | 'dci.kid.input_chosen'
  | 'dci.kid.classify_ms'
  | 'dci.kid.corrected'
  | 'dci.kid.completed_seconds';

export function emitDciKidEvent(
  name: DciKidEventName,
  detail?: Record<string, unknown>,
) {
  if (typeof window === 'undefined') return;
  try {
    window.dispatchEvent(new CustomEvent(name, { detail }));
    if (
      typeof localStorage !== 'undefined' &&
      localStorage.getItem('dci.debugTelemetry') === '1'
    ) {
      // eslint-disable-next-line no-console
      console.debug('[dci telemetry]', name, detail ?? {});
    }
  } catch {
    /* swallow — telemetry must never break the UX */
  }
}
