import { api } from './client';
import type { AxiosResponse } from 'axios';

export interface ParentContact {
  id: number;
  full_name: string;
  email: string | null;
  phone: string | null;
  school_name: string | null;
  child_name: string | null;
  child_grade: string | null;
  status: string;
  source: string;
  tags: string[];
  linked_user_id: number | null;
  consent_given: boolean;
  consent_date: string | null;
  created_by_user_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface ContactNote {
  id: number;
  parent_contact_id: number;
  note_text: string;
  created_by_user_id: number | null;
  created_at: string;
}

export interface OutreachLogEntry {
  id: number;
  parent_contact_id: number | null;
  contact_name: string | null;
  template_id: number | null;
  template_name: string | null;
  channel: string;
  status: string;
  recipient_detail: string | null;
  body_snapshot: string | null;
  sent_by_user_id: number | null;
  error_message: string | null;
  created_at: string;
}

export interface ContactStats {
  total: number;
  by_status: Record<string, number>;
  recent_outreach_count: number;
  contacts_without_consent: number;
}

export const adminContactsApi = {
  list: (params: Record<string, unknown>) =>
    api.get('/api/admin/contacts', { params }).then((r: AxiosResponse) => r.data),
  stats: () =>
    api.get('/api/admin/contacts/stats').then((r: AxiosResponse) => r.data),
  duplicates: () =>
    api.get('/api/admin/contacts/duplicates').then((r: AxiosResponse) => r.data),
  create: (data: Record<string, unknown>) =>
    api.post('/api/admin/contacts', data).then((r: AxiosResponse) => r.data),
  get: (id: number) =>
    api.get(`/api/admin/contacts/${id}`).then((r: AxiosResponse) => r.data),
  update: (id: number, data: Record<string, unknown>) =>
    api.patch(`/api/admin/contacts/${id}`, data).then((r: AxiosResponse) => r.data),
  remove: (id: number) =>
    api.delete(`/api/admin/contacts/${id}`),
  exportCsv: (params: Record<string, unknown>) =>
    api.get('/api/admin/contacts/export/csv', { params, responseType: 'blob' }),
  getNotes: (id: number) =>
    api.get(`/api/admin/contacts/${id}/notes`).then((r: AxiosResponse) => r.data),
  addNote: (id: number, note_text: string) =>
    api.post(`/api/admin/contacts/${id}/notes`, { note_text }).then((r: AxiosResponse) => r.data),
  deleteNote: (id: number, noteId: number) =>
    api.delete(`/api/admin/contacts/${id}/notes/${noteId}`),
  getOutreachHistory: (id: number) =>
    api.get(`/api/admin/contacts/${id}/outreach-history`).then((r: AxiosResponse) => r.data),
  bulkDelete: (ids: number[]) =>
    api.post('/api/admin/contacts/bulk-delete', { ids }).then((r: AxiosResponse) => r.data),
  bulkStatus: (ids: number[], status: string) =>
    api.post('/api/admin/contacts/bulk-status', { ids, status }).then((r: AxiosResponse) => r.data),
  bulkTag: (ids: number[], tag: string, action: 'add' | 'remove') =>
    api.post('/api/admin/contacts/bulk-tag', { ids, tag, action }).then((r: AxiosResponse) => r.data),
};
