import { logger } from './logger';

/**
 * CB-DCI-001 M0-10 — lightweight telemetry helper for parent evening summary.
 *
 * The DCI metrics dashboard is a fast-follow (#4149) — for M0 we just
 * dispatch a window CustomEvent (so a future analytics pipeline can hook
 * in) and forward the event to the existing `logger.info` channel so it
 * shows up in the dev console and the buffered backend log batch.
 *
 * Events emitted by this file:
 *   - dci.parent.summary_viewed      (fired once per kid+date)
 *   - dci.parent.starter_used        (toggle)
 *   - dci.parent.starter_regenerated (button)
 *   - dci.parent.deep_dive_opened    (artifact tap)
 */
export type DciTelemetryEvent =
  | 'dci.parent.summary_viewed'
  | 'dci.parent.starter_used'
  | 'dci.parent.starter_regenerated'
  | 'dci.parent.deep_dive_opened';

export function trackDciTelemetry(
  event: DciTelemetryEvent,
  payload: Record<string, unknown> = {},
): void {
  try {
    window.dispatchEvent(
      new CustomEvent('dci:telemetry', { detail: { event, payload } }),
    );
  } catch {
    // Non-fatal — never throw from telemetry.
  }
  logger.info(event, { component: 'dci', ...payload });
}
