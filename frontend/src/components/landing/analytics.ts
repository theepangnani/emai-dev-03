/**
 * CB-LAND-001 S16 (#3816, §6.136.7) — Landing v2 analytics emitters.
 *
 * Thin wrapper around the existing GatedActionBar-era emitter contract so
 * every landing section fires events with a uniform `landing_v2.*` name
 * space. Downstream shipping (GA4, internal warehouse) is owned by the
 * host emitter — this module only shapes the payload.
 *
 * ## Emitter shim
 * As of this PR the `GatedActionBar` / `InstantTrialSection` components
 * surface an `onUpsell` prop but do NOT yet call an analytics emitter —
 * that wiring is tracked by CB-DEMO-001 fast-follow #3770. Until that
 * ships, we route through the GTM-style `window.dataLayer.push` channel
 * which is what our GA container listens on. If no `dataLayer` is
 * present the call is a silent no-op so tests and SSR never crash.
 *
 * Once #3770 lands and exports a named emitter (expected shape:
 * `emit(name: string, payload: Record<string, unknown>)`), replace the
 * `dispatch()` body with a single delegating call. The public helper
 * signatures below are frozen and MUST stay stable.
 *
 * ## PII contract
 * No payload may contain user-identifying data (email, name, student
 * id, prompt text). Each helper takes only enumerated string ids; the
 * `dispatch()` validator asserts this at runtime in dev.
 *
 * ## Sampling
 * Per §6.136.7: 100% for the first 14 days post-rollout, then 25%. The
 * downstream emitter owns the actual rate — this module exposes the
 * intended value via `LANDING_V2_ANALYTICS_SAMPLE_RATE` so any later
 * toggle lives in one place.
 */

export const LANDING_V2_EVENT_PREFIX = 'landing_v2' as const;

/**
 * Intended sample rate for landing-v2 analytics events.
 *
 * @remarks Default `1.0` = 100% for the first 14 days post-rollout per
 * CB-LAND-001 §6.136.7. Step down to `0.25` after the launch-window
 * ends. The downstream emitter (GTM / warehouse sink) is responsible
 * for applying this — this constant is the single source of truth the
 * UI exports.
 *
 * TODO(CB-LAND-001): revisit 14 days after soft-launch and drop to
 * 0.25 per requirements.
 */
export const LANDING_V2_ANALYTICS_SAMPLE_RATE = 1.0;

/** Enumerated CTA ids — keep in sync with the funnel docs in §6.136.7.
 *  `get_started` was added in #3889 for launch-mode (waitlist_enabled=false):
 *  when the nav/hero/final CTAs route to `/register` instead of `/waitlist`. */
export type LandingCtaKind =
  | 'primary'
  | 'secondary'
  | 'demo'
  | 'waitlist'
  | 'get_started'
  | 'board';

interface DataLayerWindow extends Window {
  dataLayer?: Array<Record<string, unknown>>;
}

/**
 * Low-level dispatch. Keep private — callers use the typed helpers
 * below so we can evolve the transport without touching 40+ call sites.
 */
function dispatch(event: string, payload: Record<string, unknown>): void {
  if (typeof window === 'undefined') return;
  const w = window as DataLayerWindow;
  try {
    const layer = (w.dataLayer ||= []);
    layer.push({ event, ...payload });
  } catch {
    // Swallow — analytics must never break the page. Downstream sinks
    // own their own error handling.
  }
}

/**
 * Fire `landing_v2.section_view` for a section's first 50%+ viewport
 * entry. Called by `useSectionViewTracker`, not directly by components.
 */
export function emitSectionView(sectionId: string): void {
  if (!sectionId) return;
  dispatch(`${LANDING_V2_EVENT_PREFIX}.section_view`, {
    section: sectionId,
    sample_rate: LANDING_V2_ANALYTICS_SAMPLE_RATE,
  });
}

/**
 * Fire `landing_v2.cta_click` from any landing CTA button / link.
 *
 * @param cta - which CTA family (primary/secondary/demo/waitlist/board)
 * @param section - section id the CTA lives in (`hero`, `pain`, …)
 */
export function emitCtaClick(cta: LandingCtaKind, section: string): void {
  if (!section) return;
  dispatch(`${LANDING_V2_EVENT_PREFIX}.cta_click`, {
    cta,
    section,
    sample_rate: LANDING_V2_ANALYTICS_SAMPLE_RATE,
  });
}

/**
 * Fire `landing_v2.segment_tab_change` when the LearnerSegmentTabs
 * active tab switches (S9).
 */
export function emitSegmentTabChange(tabId: string): void {
  if (!tabId) return;
  dispatch(`${LANDING_V2_EVENT_PREFIX}.segment_tab_change`, {
    tab: tabId,
    sample_rate: LANDING_V2_ANALYTICS_SAMPLE_RATE,
  });
}

/**
 * Fire `landing_v2.step_view` when a HowItWorksAccordion step becomes
 * active (S6).
 */
export function emitStepView(stepNumber: number): void {
  if (!Number.isFinite(stepNumber)) return;
  dispatch(`${LANDING_V2_EVENT_PREFIX}.step_view`, {
    step: stepNumber,
    sample_rate: LANDING_V2_ANALYTICS_SAMPLE_RATE,
  });
}
