/**
 * Lightweight telemetry stub (CB-EDIGEST-002 — issue #4594, stripe E6).
 *
 * MVP behavior: every `emit(event, payload)` call is pushed onto a global
 * `window.__cb_telemetry__` accumulator (so tests can assert what fired)
 * AND logged via `console.info` so devs see events in the browser console.
 *
 * TODO Phase 2: wire to a real telemetry sink (Mixpanel / GA4 / Segment)
 * per the CB-EDIGEST-002 PRD. The current contract — `emit(event, payload?)` —
 * is the only thing call-sites should depend on; the sink is swappable.
 */

declare global {
  interface Window {
    __cb_telemetry__?: Array<{ event: string; payload?: unknown; ts: string }>;
  }
}

export interface TelemetryEntry {
  event: string;
  payload?: unknown;
  ts: string;
}

/**
 * Emit a telemetry event. Safe to call in SSR / Node contexts (it skips
 * the `window` accumulator when `window` is undefined).
 */
export function emit(event: string, payload?: unknown): void {
  const entry: TelemetryEntry = {
    event,
    payload,
    ts: new Date().toISOString(),
  };
  if (typeof window !== 'undefined') {
    window.__cb_telemetry__ = window.__cb_telemetry__ || [];
    window.__cb_telemetry__.push(entry);
  }
  console.info('[telemetry]', entry);
}
