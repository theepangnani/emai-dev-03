import { api } from './client';

export interface OutreachTemplate {
  id: number;
  name: string;
  subject: string | null;
  body_html: string | null;
  body_text: string;
  template_type: string;
  variables: string[];
  is_active: boolean;
  created_by_user_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface OutreachSendResult {
  sent_count: number;
  failed_count: number;
  errors: Array<{ contact_id: number; contact_name: string; error: string }>;
}

export interface OutreachLogEntry {
  id: number;
  contact_id: number;
  contact_name: string;
  channel: string;
  template_id: number | null;
  subject: string | null;
  status: string;
  sent_at: string;
  error_message: string | null;
}

export const adminOutreachApi = {
  listTemplates: (params?: Record<string, unknown>) =>
    api.get('/api/admin/outreach-templates', { params }).then(r => r.data),
  createTemplate: (data: Record<string, unknown>) =>
    api.post('/api/admin/outreach-templates', data).then(r => r.data),
  getTemplate: (id: number) =>
    api.get(`/api/admin/outreach-templates/${id}`).then(r => r.data),
  updateTemplate: (id: number, data: Record<string, unknown>) =>
    api.patch(`/api/admin/outreach-templates/${id}`, data).then(r => r.data),
  deleteTemplate: (id: number) =>
    api.delete(`/api/admin/outreach-templates/${id}`),
  previewTemplate: (id: number, data: { variable_values: Record<string, string> }) =>
    api.post(`/api/admin/outreach-templates/${id}/preview`, data).then(r => r.data),
  send: (data: { parent_contact_ids: number[]; template_id?: number; channel: string; custom_subject?: string; custom_body?: string }) =>
    api.post('/api/admin/outreach/send', data).then(r => r.data) as Promise<OutreachSendResult>,
  getLog: (params?: Record<string, unknown>) =>
    api.get('/api/admin/outreach/log', { params }).then(r => r.data),
  getLogEntry: (id: number) =>
    api.get(`/api/admin/outreach/log/${id}`).then(r => r.data),
  getStats: () =>
    api.get('/api/admin/outreach/stats').then(r => r.data),
};
