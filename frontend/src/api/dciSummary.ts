import { api } from './client';

/**
 * CB-DCI-001 M0-10 — Parent evening summary API client.
 *
 * Owns the read paths for `/api/dci/summary/{kidId}/{date}` plus the
 * conversation-starter feedback PATCH (M0-6 owns the data write; this
 * file only types and exposes the call so the UI can fire it).
 *
 * Backend routes are owned by M0-4 / M0-6 and may not be merged when
 * this file lands — tests mock these functions via `vi.mock`.
 */

export type DciDeadlineUrgency = 'amber' | 'red';

export interface DciDeadlineChip {
  id: number;
  label: string;
  /** ISO date — when the deadline falls */
  due_date: string;
  urgency: DciDeadlineUrgency;
  /** Set when the artifact was captured on paper and not seen on Google Classroom */
  paper_only?: boolean;
  not_yet_on_classroom?: boolean;
}

export interface DciSubjectBullet {
  /** Short subject label, e.g., "Math" */
  subject: string;
  /** Plain-text body of the bullet — kept ≤ ~140 chars by the summary prompt */
  text: string;
}

export interface DciConversationStarter {
  id: number;
  text: string;
  was_used?: boolean | null;
}

export interface DciArtifact {
  id: number;
  artifact_type: 'photo' | 'voice' | 'text';
  /** Short caption / preview text */
  preview: string;
  /** Optional thumbnail URL for photos / waveform pills for voice */
  thumbnail_url?: string | null;
}

export interface DciDailySummary {
  /** id of the underlying ai_summaries row */
  id: number;
  kid_id: number;
  kid_name: string;
  /** ISO date (yyyy-mm-dd) */
  summary_date: string;
  /** 30-second-read body — three subject bullets */
  bullets: DciSubjectBullet[];
  upcoming: DciDeadlineChip[];
  conversation_starter: DciConversationStarter | null;
  artifacts: DciArtifact[];
  generated_at: string;
}

/**
 * Two response shapes:
 *   - 200 + summary: a check-in exists for the day
 *   - 200 + null + reason='no_checkin_today': empty state
 *   - 200 + null + reason='first_30_days': pattern stub state
 */
export interface DciSummaryResponse {
  summary: DciDailySummary | null;
  state: 'ready' | 'no_checkin_today' | 'first_30_days';
}

export type ConversationStarterFeedback =
  | 'thumbs_up'
  | 'regenerate'
  // S-5 (#4218): explicit untoggle signal so the parent can clear the
  // "I used this" state. Backend M0-6 owner: interpret as `was_used=false`.
  | 'undo_used';

export interface ConversationStarterFeedbackResponse {
  starter: DciConversationStarter;
}

export const dciSummaryApi = {
  /**
   * GET /api/dci/summary/{kidId}/{date}
   * Backend owner: M0-4 (or M0-6). May 404 until merged — tests mock.
   */
  getSummary: async (
    kidId: number,
    date: string,
  ): Promise<DciSummaryResponse> => {
    const resp = await api.get<DciSummaryResponse>(
      `/api/dci/summary/${kidId}/${date}`,
    );
    return resp.data;
  },

  /**
   * PATCH /api/dci/conversation-starters/{id}/feedback
   * Backend owner: M0-6.
   */
  submitStarterFeedback: async (
    starterId: number,
    feedback: ConversationStarterFeedback,
  ): Promise<ConversationStarterFeedbackResponse> => {
    const resp = await api.patch<ConversationStarterFeedbackResponse>(
      `/api/dci/conversation-starters/${starterId}/feedback`,
      { feedback },
    );
    return resp.data;
  },
};
