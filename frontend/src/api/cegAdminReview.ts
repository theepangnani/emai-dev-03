/**
 * CB-CMCP-001 M0-B 0B-3b — Curriculum-admin review API client (#4429).
 *
 * Typed Axios wrappers for the four endpoints under
 * `/api/ceg/admin/review/*` shipped by stripe 0B-3a (PR #4432).
 * Pydantic response shapes mirror `PendingExpectationResponse` and the
 * `EditExpectationRequest` schemas in `app/api/routes/ceg_admin_review.py`.
 */
import { api } from './client';

export interface CEGPendingExpectation {
  id: number;
  ministry_code: string;
  cb_code: string | null;
  subject_id: number;
  strand_id: number;
  grade: number;
  expectation_type: string; // 'overall' | 'specific'
  parent_oe_id: number | null;
  description: string;
  curriculum_version_id: number;
  active: boolean;
  review_state: string; // 'pending' | 'accepted' | 'rejected'
  reviewed_by_user_id: number | null;
  reviewed_at: string | null;
  review_notes: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface CEGEditExpectationPayload {
  description?: string;
  ministry_code?: string;
  strand_id?: number;
  expectation_type?: string;
  parent_oe_id?: number | null;
  review_notes?: string;
}

export interface CEGRejectPayload {
  review_notes?: string;
}

export const cegAdminReviewApi = {
  /** List all expectations with `review_state='pending'`. */
  async listPending(): Promise<CEGPendingExpectation[]> {
    const { data } = await api.get<CEGPendingExpectation[]>(
      '/api/ceg/admin/review/pending',
    );
    return data;
  },

  /** Accept a pending expectation: sets active=true + review_state='accepted'. */
  async accept(id: number): Promise<CEGPendingExpectation> {
    const { data } = await api.post<CEGPendingExpectation>(
      `/api/ceg/admin/review/${id}/accept`,
    );
    return data;
  },

  /** Reject a pending expectation. Optional review_notes. */
  async reject(
    id: number,
    payload?: CEGRejectPayload,
  ): Promise<CEGPendingExpectation> {
    const { data } = await api.post<CEGPendingExpectation>(
      `/api/ceg/admin/review/${id}/reject`,
      payload ?? {},
    );
    return data;
  },

  /** Edit reviewable fields on an expectation. Partial update. */
  async edit(
    id: number,
    payload: CEGEditExpectationPayload,
  ): Promise<CEGPendingExpectation> {
    const { data } = await api.patch<CEGPendingExpectation>(
      `/api/ceg/admin/review/${id}`,
      payload,
    );
    return data;
  },
};
