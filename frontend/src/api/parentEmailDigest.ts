import { api } from './client';

// Types matching backend schemas
export interface MonitoredEmail {
  id: number;
  integration_id: number;
  email_address: string | null;
  sender_name: string | null;
  label: string | null;
  created_at: string;
}

export interface EmailDigestIntegration {
  id: number;
  parent_id: number;
  gmail_address: string;
  google_id: string | null;
  child_school_email: string | null;
  child_first_name: string | null;
  connected_at: string;
  last_synced_at: string | null;
  is_active: boolean;
  paused_until: string | null;
  created_at: string;
  updated_at: string;
  monitored_emails: MonitoredEmail[];
  whatsapp_phone: string | null;
  whatsapp_verified: boolean;
}

export interface EmailDigestSettings {
  id: number;
  integration_id: number;
  digest_enabled: boolean;
  delivery_time: string;
  timezone: string;
  digest_format: string;
  delivery_channels: string;
  notify_on_empty: boolean;
  updated_at: string;
}

export interface GmailAuthUrlResponse {
  authorization_url: string;
  state: string;
}

export interface GmailCallbackResponse {
  status: string;
  gmail_address: string | null;
  integration_id: number | null;
}

// API functions
export const getGmailAuthUrl = (redirect_uri: string) =>
  api.get<GmailAuthUrlResponse>('/api/parent/email-digest/gmail/auth-url', {
    params: { redirect_uri },
  });

export const connectGmail = (code: string, state: string, redirect_uri: string) =>
  api.post<GmailCallbackResponse>('/api/parent/email-digest/gmail/callback', {
    code,
    state,
    redirect_uri,
  });

export const updateIntegration = (integrationId: number, data: Partial<Pick<EmailDigestIntegration, 'child_school_email' | 'child_first_name' | 'is_active' | 'paused_until'>>) =>
  api.patch<EmailDigestIntegration>(`/api/parent/email-digest/integrations/${integrationId}`, data);

export const listIntegrations = () =>
  api.get<EmailDigestIntegration[]>('/api/parent/email-digest/integrations');

export const getSettings = (integrationId: number) =>
  api.get<EmailDigestSettings>(`/api/parent/email-digest/settings/${integrationId}`);

export const updateSettings = (integrationId: number, data: Partial<EmailDigestSettings>) =>
  api.put<EmailDigestSettings>(`/api/parent/email-digest/settings/${integrationId}`, data);

export const pauseIntegration = (integrationId: number) =>
  api.post<EmailDigestIntegration>(`/api/parent/email-digest/integrations/${integrationId}/pause`);

export const resumeIntegration = (integrationId: number) =>
  api.post<EmailDigestIntegration>(`/api/parent/email-digest/integrations/${integrationId}/resume`);

export interface DigestDeliveryLog {
  id: number;
  parent_id: number;
  integration_id: number;
  email_count: number;
  digest_content: string | null;
  digest_length_chars: number | null;
  delivered_at: string;
  channels_used: string | null;
  status: string;
}

export const getLogs = (params?: { integration_id?: number; skip?: number; limit?: number }) =>
  api.get<DigestDeliveryLog[]>('/api/parent/email-digest/logs', { params });

export const getLog = (logId: number) =>
  api.get<DigestDeliveryLog>(`/api/parent/email-digest/logs/${logId}`);

export const triggerSync = (integrationId: number) =>
  api.post<EmailDigestIntegration>(`/api/parent/email-digest/integrations/${integrationId}/sync`);

export const verifyForwarding = (integrationId: number) =>
  api.post(`/api/parent/email-digest/integrations/${integrationId}/verify-forwarding`);

export interface SendDigestChannelStatus {
  in_app: boolean | null;
  email: boolean | null;
  whatsapp: boolean | null;
}

export interface SendDigestResponse {
  status: string; // "delivered" | "partial" | "failed" | "skipped"
  email_count: number;
  message: string;
  // #3880: per-channel outcomes. `null` = channel not requested, `true` = sent, `false` = failed.
  channel_status?: SendDigestChannelStatus | null;
  // #3894: machine-readable reason for skipped status. One of
  // "already_delivered", "no_settings", "no_new_emails", "no_eligible_channels",
  // or null/undefined when status != "skipped". Frontends use this to gate UI —
  // e.g., the "Open preferences" link only makes sense for "no_eligible_channels".
  reason?: string | null;
}

export const sendDigestNow = (integrationId: number) =>
  api.post<SendDigestResponse>(
    `/api/parent/email-digest/integrations/${integrationId}/send-digest`
  );

// #4483: parent-scoped Send-Digest-Now. Used by the unified multi-kid UI so
// the V2 flag can route to `send_unified_digest_for_parent` (one envelope
// across all integrations) and produce multi-kid framing in subject + body.
// Single-kid / legacy callers still use `sendDigestNow` above.
export const sendDigestNowForParent = (sinceHours = 24) =>
  api.post<SendDigestResponse>('/api/parent/email-digest/send-now', null, {
    params: { since_hours: sinceHours },
  });

// Monitored emails (#3178)
export const listMonitoredEmails = (integrationId: number) =>
  api.get<MonitoredEmail[]>(`/api/parent/email-digest/integrations/${integrationId}/monitored-emails`);

export const addMonitoredEmail = (integrationId: number, data: { email_address?: string; sender_name?: string; label?: string }) =>
  api.post<MonitoredEmail>(`/api/parent/email-digest/integrations/${integrationId}/monitored-emails`, data);

export const removeMonitoredEmail = (integrationId: number, emailId: number) =>
  api.delete(`/api/parent/email-digest/integrations/${integrationId}/monitored-emails/${emailId}`);

// WhatsApp (#3592)
export interface WhatsAppOTPResponse {
  message: string;
  phone: string;
}

export async function sendWhatsAppOTP(
  integrationId: number,
  phone: string,
): Promise<WhatsAppOTPResponse> {
  const res = await api.post<WhatsAppOTPResponse>(
    `/api/parent/email-digest/integrations/${integrationId}/whatsapp/send-otp`,
    { phone },
  );
  return res.data;
}

export async function verifyWhatsAppOTP(
  integrationId: number,
  otpCode: string,
): Promise<WhatsAppOTPResponse> {
  const res = await api.post<WhatsAppOTPResponse>(
    `/api/parent/email-digest/integrations/${integrationId}/whatsapp/verify-otp`,
    { otp_code: otpCode },
  );
  return res.data;
}

export async function disconnectWhatsApp(integrationId: number): Promise<void> {
  await api.delete(`/api/parent/email-digest/integrations/${integrationId}/whatsapp`);
}

// Unified multi-kid digest v2 (#4012)
// -----------------------------------------------------------------------------
// Parent-level (not integration-level) child profiles, school emails, and
// monitored senders. Server endpoints from Stream 2 (#4014).

export interface ChildSchoolEmail {
  id: number;
  child_profile_id: number;
  email_address: string;
  /** ISO timestamp of last matched forwarded message, null if never seen. */
  forwarding_seen_at: string | null;
  created_at: string;
}

export interface ChildProfile {
  id: number;
  parent_id: number;
  student_id: number | null;
  first_name: string;
  school_emails: ChildSchoolEmail[];
  created_at: string;
}

// Aliases kept for call-sites that use the `Parent*`-prefixed naming
// introduced by Stream 5 (#4017). Keep both to avoid churn across streams.
export type ParentChildSchoolEmail = ChildSchoolEmail;
export type ParentChildProfile = ChildProfile;

export interface MonitoredSenderAssignment {
  child_profile_id: number;
  first_name: string;
}

export interface MonitoredSender {
  id: number;
  parent_id: number;
  email_address: string;
  sender_name: string | null;
  label: string | null;
  /** When true, sender applies to ALL current + future kids. */
  applies_to_all: boolean;
  /**
   * Plain list of assigned profile IDs. Always present (defaults to []).
   * Backend returns this alongside `assignments` for backward compat.
   */
  child_profile_ids: number[];
  /**
   * Populated only when applies_to_all=false. Optional because pre-#4082
   * backends returned only child_profile_ids — callers must handle it
   * being missing when rendering chips with first_name.
   */
  assignments?: MonitoredSenderAssignment[];
  created_at: string;
}

/** Either "all" (applies_to_all=true) or an explicit list of child_profile ids. */
export type SenderKidSelection = 'all' | number[];

export interface AddMonitoredSenderPayload {
  email_address: string;
  sender_name?: string;
  label?: string;
  child_profile_ids: SenderKidSelection;
}

export const listChildProfiles = () =>
  api.get<ChildProfile[]>('/api/parent/child-profiles');

/**
 * Idempotent profile creation (#4044). Dedupes server-side on
 * `(parent_id, student_id)` when `student_id` is provided, otherwise on
 * `(parent_id, LOWER(first_name))`. Used by both the unified Email Digest
 * page (auto-create on first school email for a kid without a profile)
 * and the setup wizard.
 */
export const createChildProfile = (data: { student_id?: number | null; first_name: string }) =>
  api.post<ChildProfile>('/api/parent/child-profiles', data);

export const addChildSchoolEmail = (profileId: number, email_address: string) =>
  api.post<ChildSchoolEmail>(
    `/api/parent/child-profiles/${profileId}/school-emails`,
    { email_address },
  );

export const removeChildSchoolEmail = (profileId: number, emailId: number) =>
  api.delete(`/api/parent/child-profiles/${profileId}/school-emails/${emailId}`);

export const listMonitoredSenders = () =>
  api.get<MonitoredSender[]>('/api/parent/email-digest/monitored-senders');

export const addMonitoredSender = (data: AddMonitoredSenderPayload) =>
  api.post<MonitoredSender>('/api/parent/email-digest/monitored-senders', data);

export const removeMonitoredSender = (id: number) =>
  api.delete(`/api/parent/email-digest/monitored-senders/${id}`);

export const updateSenderAssignments = (
  id: number,
  child_profile_ids: SenderKidSelection,
) =>
  api.patch<MonitoredSender>(`/api/parent/email-digest/monitored-senders/${id}/assignments`, {
    child_profile_ids,
  });

// Auto-discovered school addresses (#4329) — surfaced by the worker when
// a forwarded email lands with a school-looking To: address that isn't
// registered for any kid.
export interface DiscoveredSchoolEmail {
  id: number;
  email_address: string;
  sample_sender: string | null;
  occurrences: number;
  first_seen_at: string;
  last_seen_at: string;
}

export const listDiscoveredSchoolEmails = () =>
  api.get<DiscoveredSchoolEmail[]>('/api/parent/email-digest/discovered-school-emails');

export const assignDiscoveredSchoolEmail = (id: number, child_profile_id: number) =>
  api.post(`/api/parent/email-digest/discovered-school-emails/${id}/assign`, { child_profile_id });

export const dismissDiscoveredSchoolEmail = (id: number) =>
  api.delete(`/api/parent/email-digest/discovered-school-emails/${id}`);

// ---------------------------------------------------------------------------
// Dashboard (CB-EDIGEST-002 — #4594)
// ---------------------------------------------------------------------------
// `GET /api/parent/email-digest/dashboard` is the new aggregated endpoint
// that powers the Email-Digest Dashboard surface (E1 sibling stripe).
// Shape lives in `pages/parent/dashboard/types.ts` so backend + frontend
// stripes import from the same source.
import type { DashboardResponse } from '../pages/parent/dashboard/types';

export type { DashboardResponse } from '../pages/parent/dashboard/types';

/**
 * Fetch the dashboard response. The `since` window controls how far back
 * the server scans monitored emails — defaults to "today" per the PRD.
 */
export const getDashboard = (since: string = 'today') =>
  api.get<DashboardResponse>('/api/parent/email-digest/dashboard', {
    params: { since },
  });
