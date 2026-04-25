/**
 * Daily Check-In Ritual (DCI) API client — CB-DCI-001 M0-9
 *
 * Backend endpoints owned by M0-4 (POST /checkin, /status, /correct) and
 * M0-8 (GET /streak). Types here are written against the design lock
 * (`docs/design/CB-DCI-001-daily-checkin.md` § 9 + § 10).
 *
 * Tests mock this module directly via `vi.mock('../api/dci', ...)` so the
 * API surface deliberately stays small and explicit.
 */
import { api, AI_TIMEOUT } from './client';

// --- Types ---

export type DciArtifactType = 'photo' | 'voice' | 'text';

/** Classification chip — `subject + topic + deadline` shown back to the kid. */
export interface DciClassification {
  artifact_type: DciArtifactType;
  subject: string | null;
  topic: string | null;
  deadline_iso: string | null;
  confidence: number | null;
  corrected_by_kid: boolean;
}

export type DciCheckinStatus = 'pending' | 'classified' | 'failed';

export interface DciCheckinStatusResponse {
  checkin_id: number;
  status: DciCheckinStatus;
  classifications: DciClassification[];
}

export interface DciCheckinCreateResponse {
  checkin_id: number;
  status: DciCheckinStatus;
  /** Set when classifier returned synchronously inside the 202 window. */
  classifications?: DciClassification[];
}

export interface DciStreakResponse {
  kid_id: number;
  current_streak: number;
  longest_streak: number;
  last_checkin_date: string | null;
  /** Most recent voice sentiment (-1..1). Null when no voice in history. */
  last_voice_sentiment?: number | null;
}

export interface DciCorrectionPayload {
  artifact_type: DciArtifactType;
  subject?: string;
  topic?: string;
  deadline_iso?: string | null;
}

// --- API ---

export const dciApi = {
  /**
   * Multi-artifact check-in submit. Backend returns 202 with the new
   * `checkin_id`. Classifications either ride along (sync path) or arrive
   * via `getStatus` polling (async path).
   */
  submitCheckin: async (form: FormData): Promise<DciCheckinCreateResponse> => {
    const { data } = await api.post<DciCheckinCreateResponse>(
      '/api/dci/checkin',
      form,
      {
        ...AI_TIMEOUT,
        headers: { 'Content-Type': 'multipart/form-data' },
      },
    );
    return data;
  },

  getStatus: async (checkinId: number): Promise<DciCheckinStatusResponse> => {
    const { data } = await api.get<DciCheckinStatusResponse>(
      `/api/dci/checkin/${checkinId}/status`,
    );
    return data;
  },

  correct: async (
    checkinId: number,
    payload: DciCorrectionPayload,
  ): Promise<DciClassification> => {
    const { data } = await api.patch<DciClassification>(
      `/api/dci/checkin/${checkinId}/correct`,
      payload,
    );
    return data;
  },

  getStreak: async (kidId: number): Promise<DciStreakResponse> => {
    const { data } = await api.get<DciStreakResponse>(
      `/api/dci/streak/${kidId}`,
    );
    return data;
  },
};
