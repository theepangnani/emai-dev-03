/**
 * Shared TypeScript types for the parent Email-Digest Dashboard surface
 * (CB-EDIGEST-002 — issue #4594, stripe E6).
 *
 * These types describe the shape of the response from the new
 * `GET /api/parent/email-digest/dashboard` endpoint (E1) and are consumed
 * by the dashboard components (E2-E5) plus the orchestrator (this stripe).
 *
 * Keep this file additive — sibling stripes also import from it.
 */

/**
 * A single high-priority item shown in the "Today / This week" Today section.
 */
export interface UrgentItem {
  id: string;
  title: string;
  /** ISO date or null when no due date is parseable from the source email. */
  due_date: string | null;
  course_or_context: string | null;
  source_email_id: string;
}

/**
 * Per-kid section returned by the dashboard endpoint. Holds both the
 * urgent-today items and the 7-day forecast buckets.
 */
export interface KidSection {
  id: number;
  first_name: string;
  urgent_items: UrgentItem[];
  weekly_deadlines: DayBucket[];
  /** True when there's nothing urgent + nothing on the week grid for this kid. */
  all_clear: boolean;
}

/**
 * A deadline rendered in the WeekGrid 7-day forecast.
 * Distinct from `UrgentItem` (no `due_date` because the bucket carries the day).
 */
export interface WeekDeadline {
  id: string;
  title: string;
  course_or_context: string | null;
  source_email_id: string;
}

/**
 * One 24-hour bucket in the WeekGrid 7-day forecast.
 */
export interface DayBucket {
  /** ISO date (YYYY-MM-DD). */
  day: string;
  /** Short weekday label, e.g. "Mon". */
  weekday: string;
  items: WeekDeadline[];
  /** True when `day` is strictly before today (UI styles it as past-due/dimmed). */
  is_past: boolean;
}

/**
 * Discriminator for which empty-state variant `EmptyStates` should render.
 * `null` (in `DashboardResponse.empty_state`) means "render the normal grid".
 */
export type EmptyStateKind =
  | 'calm'
  | 'no_kids'
  | 'paused'
  | 'auth_expired'
  | 'first_run'
  | 'legacy_blob';

/**
 * Top-level response shape from `GET /api/parent/email-digest/dashboard`.
 */
export interface DashboardResponse {
  kids: KidSection[];
  /**
   * When non-null, the dashboard renders the matching `EmptyStates` variant
   * INSTEAD of the kid grid. The endpoint owns this discriminator so the
   * frontend doesn't have to re-derive "is everything calm / paused / etc."
   */
  empty_state: EmptyStateKind | null;
  /** ISO timestamp the response was generated server-side. */
  refreshed_at: string;
  /** ISO timestamp of the last delivered digest, null if never. */
  last_digest_at: string | null;
}

/**
 * Item shape passed to the `ItemDrilldownModal`. Extends the urgent-item
 * shape with optional source-email metadata fetched on click.
 */
export interface DrilldownItem extends UrgentItem {
  source_email_subject?: string;
  source_email_body?: string;
  source_email_from?: string;
  source_email_received?: string;
}
