import { api } from './client';

export type NewsletterStatus = 'draft' | 'scheduled' | 'sent';
export type NewsletterAudience = 'all' | 'parents' | 'teachers' | 'students';
export type NewsletterTone = 'formal' | 'friendly' | 'informative';

export interface Newsletter {
  id: number;
  created_by: number;
  title: string;
  subject: string;
  content: string;
  html_content?: string | null;
  audience: NewsletterAudience;
  status: NewsletterStatus;
  scheduled_at?: string | null;
  sent_at?: string | null;
  recipient_count: number;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface NewsletterCreate {
  title: string;
  subject: string;
  content: string;
  html_content?: string;
  audience?: NewsletterAudience;
}

export interface NewsletterUpdate {
  title?: string;
  subject?: string;
  content?: string;
  html_content?: string;
  audience?: NewsletterAudience;
}

export interface NewsletterGenerateRequest {
  topic: string;
  key_points: string[];
  audience?: NewsletterAudience;
  tone?: NewsletterTone;
}

export interface NewsletterSendResponse {
  sent_count: number;
  failed_count: number;
  newsletter_id: number;
}

export interface NewsletterTemplate {
  id: number;
  name: string;
  description: string;
  content_template: string;
  is_active: boolean;
  created_at?: string | null;
}

export const newslettersApi = {
  list: async (): Promise<Newsletter[]> => {
    const { data } = await api.get<Newsletter[]>('/api/newsletters/');
    return data;
  },

  get: async (id: number): Promise<Newsletter> => {
    const { data } = await api.get<Newsletter>(`/api/newsletters/${id}`);
    return data;
  },

  create: async (payload: NewsletterCreate): Promise<Newsletter> => {
    const { data } = await api.post<Newsletter>('/api/newsletters/', payload);
    return data;
  },

  update: async (id: number, payload: NewsletterUpdate): Promise<Newsletter> => {
    const { data } = await api.patch<Newsletter>(`/api/newsletters/${id}`, payload);
    return data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/api/newsletters/${id}`);
  },

  generate: async (payload: NewsletterGenerateRequest): Promise<Newsletter> => {
    const { data } = await api.post<Newsletter>('/api/newsletters/generate', payload);
    return data;
  },

  send: async (id: number): Promise<NewsletterSendResponse> => {
    const { data } = await api.post<NewsletterSendResponse>(`/api/newsletters/${id}/send`);
    return data;
  },

  schedule: async (id: number, scheduledAt: string): Promise<Newsletter> => {
    const { data } = await api.post<Newsletter>(`/api/newsletters/${id}/schedule`, {
      scheduled_at: scheduledAt,
    });
    return data;
  },

  getTemplates: async (): Promise<NewsletterTemplate[]> => {
    const { data } = await api.get<NewsletterTemplate[]>('/api/newsletters/templates');
    return data;
  },
};
