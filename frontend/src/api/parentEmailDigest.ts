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

export const sendDigestNow = (integrationId: number) =>
  api.post<{ status: string; email_count: number; message: string }>(
    `/api/parent/email-digest/integrations/${integrationId}/send-digest`
  );

// Monitored emails (#3178)
export const listMonitoredEmails = (integrationId: number) =>
  api.get<MonitoredEmail[]>(`/api/parent/email-digest/integrations/${integrationId}/monitored-emails`);

export const addMonitoredEmail = (integrationId: number, data: { email_address?: string; sender_name?: string; label?: string }) =>
  api.post<MonitoredEmail>(`/api/parent/email-digest/integrations/${integrationId}/monitored-emails`, data);

export const removeMonitoredEmail = (integrationId: number, emailId: number) =>
  api.delete(`/api/parent/email-digest/integrations/${integrationId}/monitored-emails/${emailId}`);
