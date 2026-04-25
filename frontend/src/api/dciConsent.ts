// CB-DCI-001 M0-11 — DCI consent API client (#4148)
import { api } from './client';

export type RetentionDays = 90 | 365 | 1095;

export interface DciConsent {
  parent_id: number;
  kid_id: number;
  photo_ok: boolean;
  voice_ok: boolean;
  ai_ok: boolean;
  retention_days: number;
  dci_enabled: boolean;
  muted: boolean;
  /** HH:MM 24h, e.g. "15:15" */
  kid_push_time: string;
  /** HH:MM 24h, e.g. "19:00" */
  parent_push_time: string;
  allowed_retention_days: number[];
}

export interface DciConsentList {
  items: DciConsent[];
}

export interface DciConsentUpdate {
  kid_id: number;
  photo_ok?: boolean;
  voice_ok?: boolean;
  ai_ok?: boolean;
  retention_days?: number;
  dci_enabled?: boolean;
  muted?: boolean;
  kid_push_time?: string;
  parent_push_time?: string;
}

export const dciConsentApi = {
  list: async (): Promise<DciConsent[]> => {
    const response = await api.get<DciConsentList>('/api/dci/consent');
    return response.data.items;
  },
  get: async (kidId: number): Promise<DciConsent> => {
    const response = await api.get<DciConsent>(`/api/dci/consent/${kidId}`);
    return response.data;
  },
  upsert: async (update: DciConsentUpdate): Promise<DciConsent> => {
    const response = await api.post<DciConsent>('/api/dci/consent', update);
    return response.data;
  },
};
