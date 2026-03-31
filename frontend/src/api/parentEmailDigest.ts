import { api } from './client';

export interface EmailDigestIntegration {
  id: number;
  parent_email: string;
  child_school_email: string;
  child_first_name: string;
  status: string;
  created_at: string;
}

export interface EmailDigestSettings {
  integration_id: number;
  delivery_time: string;
  timezone: string;
  digest_format: string;
  channels: string[];
}

export interface GmailAuthUrlResponse {
  auth_url: string;
}

export interface GmailCallbackResponse {
  integration_id: number;
  parent_email: string;
  status: string;
}

export const parentEmailDigestApi = {
  getGmailAuthUrl: async () => {
    const response = await api.get('/api/parent/email-digest/gmail/auth-url');
    return response.data as GmailAuthUrlResponse;
  },

  connectGmail: async (code: string) => {
    const response = await api.post('/api/parent/email-digest/gmail/callback', { code });
    return response.data as GmailCallbackResponse;
  },

  listIntegrations: async () => {
    const response = await api.get('/api/parent/email-digest/integrations');
    return response.data as EmailDigestIntegration[];
  },

  getSettings: async (integrationId: number) => {
    const response = await api.get(`/api/parent/email-digest/settings/${integrationId}`);
    return response.data as EmailDigestSettings;
  },

  updateSettings: async (integrationId: number, data: Partial<Omit<EmailDigestSettings, 'integration_id'>>) => {
    const response = await api.put(`/api/parent/email-digest/settings/${integrationId}`, data);
    return response.data as EmailDigestSettings;
  },

  pauseIntegration: async (id: number) => {
    const response = await api.post(`/api/parent/email-digest/integrations/${id}/pause`);
    return response.data;
  },

  resumeIntegration: async (id: number) => {
    const response = await api.post(`/api/parent/email-digest/integrations/${id}/resume`);
    return response.data;
  },
};
