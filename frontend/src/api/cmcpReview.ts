/**
 * CB-CMCP-001 M3-A 3A-2 (#4582) — Teacher Review Queue API client.
 *
 * Typed Axios wrappers for the six endpoints under `/api/cmcp/review/*`
 * shipped by stripe 3A-1 (PR #4608, `app/api/routes/cmcp_review.py`).
 *
 * Pydantic response shapes mirror `ReviewQueueItem`,
 * `ReviewArtifactDetail`, and `EditHistoryEntry` exactly.
 */
import { api } from './client';

export interface ReviewQueueItem {
  id: number;
  title: string;
  guide_type: string;
  state: string;
  course_id: number | null;
  user_id: number;
  se_codes: string[];
  requested_persona: string | null;
  created_at: string | null;
}

export interface ReviewQueueResponse {
  items: ReviewQueueItem[];
  total: number;
  page: number;
  limit: number;
}

export interface EditHistoryEntry {
  editor_id: number;
  edit_at: string;
  before_snippet: string;
  after_snippet: string;
}

export interface ReviewArtifactDetail {
  id: number;
  user_id: number;
  course_id: number | null;
  title: string;
  content: string;
  guide_type: string;
  state: string;
  se_codes: string[];
  voice_module_hash: string | null;
  requested_persona: string | null;
  board_id: string | null;
  alignment_score: number | null;
  ceg_version: number | null;
  class_context_envelope_summary: Record<string, unknown> | null;
  edit_history: EditHistoryEntry[];
  reviewed_by_user_id: number | null;
  reviewed_at: string | null;
  rejection_reason: string | null;
  created_at: string | null;
}

export type ReviewSortField = 'created_at' | 'content_type' | 'subject';

export interface QueueListParams {
  page?: number;
  limit?: number;
  sort_by?: ReviewSortField;
}

export interface EditDeltaPayload {
  content: string;
}

export interface RejectPayload {
  reason: string;
}

/**
 * Mirrors `app/schemas/cmcp.py::CMCPGenerateRequest`. Used as the inner
 * `request` body for `POST /api/cmcp/review/{id}/regenerate`.
 *
 * 3A-2 doesn't drive a full regenerate UX — that's 3A-4's scope (#4584).
 * We expose the wire shape so 3A-4 can drop in without touching the
 * client.
 */
export interface CmcpGenerateRequest {
  grade: number;
  subject_code: string;
  strand_code?: string | null;
  topic?: string | null;
  content_type: string;
  difficulty?: string;
  target_persona?: string | null;
  course_id?: number | null;
}

export interface RegeneratePayload {
  request: CmcpGenerateRequest;
}

export const cmcpReviewApi = {
  /** Paginated PENDING_REVIEW queue. TEACHER → own classes, ADMIN → all. */
  async listQueue(params: QueueListParams = {}): Promise<ReviewQueueResponse> {
    const { data } = await api.get<ReviewQueueResponse>(
      '/api/cmcp/review/queue',
      { params },
    );
    return data;
  },

  /** Full artifact + review metadata. 404 covers both "no row" + "no access". */
  async getArtifact(artifactId: number): Promise<ReviewArtifactDetail> {
    const { data } = await api.get<ReviewArtifactDetail>(
      `/api/cmcp/review/${artifactId}`,
    );
    return data;
  },

  /** Apply an edit delta + append to `edit_history`. Gated to PENDING_REVIEW/REJECTED/DRAFT. */
  async editArtifact(
    artifactId: number,
    payload: EditDeltaPayload,
  ): Promise<ReviewArtifactDetail> {
    const { data } = await api.patch<ReviewArtifactDetail>(
      `/api/cmcp/review/${artifactId}`,
      payload,
    );
    return data;
  },

  /** PENDING_REVIEW → APPROVED. */
  async approve(artifactId: number): Promise<ReviewArtifactDetail> {
    const { data } = await api.post<ReviewArtifactDetail>(
      `/api/cmcp/review/${artifactId}/approve`,
    );
    return data;
  },

  /** PENDING_REVIEW → REJECTED. `reason` required (1-2000 chars). */
  async reject(
    artifactId: number,
    payload: RejectPayload,
  ): Promise<ReviewArtifactDetail> {
    const { data } = await api.post<ReviewArtifactDetail>(
      `/api/cmcp/review/${artifactId}/reject`,
      payload,
    );
    return data;
  },

  /** Re-run prompt build + replace content. State stays PENDING_REVIEW. */
  async regenerate(
    artifactId: number,
    payload: RegeneratePayload,
  ): Promise<ReviewArtifactDetail> {
    const { data } = await api.post<ReviewArtifactDetail>(
      `/api/cmcp/review/${artifactId}/regenerate`,
      payload,
    );
    return data;
  },
};
