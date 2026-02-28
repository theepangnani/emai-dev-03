import { api } from './client';

export interface ConsentPreferences {
  essential: boolean;
  analytics: boolean;
  ai_processing: boolean;
  consent_given_at?: string | null;
}

export interface ConsentStatus {
  student_id: number;
  consent_status: string;
  age: number | null;
  requires_parent_consent: boolean;
  requires_student_consent: boolean;
  parent_consent_given: boolean;
  student_consent_given: boolean;
  parent_consent_given_at: string | null;
  student_consent_given_at: string | null;
}

export const consentApi = {
  /** Update cookie/data consent preferences (#797). */
  updatePreferences: async (prefs: { analytics: boolean; ai_processing: boolean }) => {
    const resp = await api.put('/api/users/me/consent-preferences', {
      essential: true,
      ...prefs,
    });
    return resp.data as ConsentPreferences;
  },

  /** Get current consent preferences (#797). */
  getPreferences: async () => {
    const resp = await api.get('/api/users/me/consent-preferences');
    return resp.data as ConsentPreferences;
  },

  /** Get consent status for a student (#783). */
  getStatus: async (studentId: number) => {
    const resp = await api.get(`/api/consent/status/${studentId}`);
    return resp.data as ConsentStatus;
  },

  /** Student gives their own consent (#783). */
  giveConsent: async () => {
    const resp = await api.post('/api/consent/give', { accept: true });
    return resp.data as { message: string; consent_status: string };
  },

  /** Parent gives consent for a child (#783). */
  giveConsentForChild: async (studentId: number) => {
    const resp = await api.post(`/api/consent/give-for-child/${studentId}`);
    return resp.data as { message: string; consent_status: string };
  },
};
