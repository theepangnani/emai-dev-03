/**
 * CB-CMCP-001 M3β follow-up #4694 — Student artifact view API client.
 *
 * Thin wrapper around `GET /api/cmcp/artifacts/{artifact_id}/student-view`.
 * The endpoint returns the artifact title + raw content + guide_type for
 * the LTI-launched student page (`/student/artifact/:artifact_id`).
 *
 * Why a separate endpoint from `/parent-companion`: the parent-companion
 * endpoint requires `requested_persona == 'parent'` and returns a
 * 5-section coaching shape; LTI-launched STUDENT users need the actual
 * artifact content, not coaching scaffolding for a parent.
 */
import { api } from './client';

export interface StudentArtifactView {
  artifact_id: number;
  title: string;
  content: string;
  guide_type: string;
}

export const cmcpStudentArtifactApi = {
  /**
   * Fetch the student-view projection for a given artifact id.
   * Throws (axios error) on 401/403/404; the page component catches
   * and renders the error state.
   */
  get: async (artifactId: string | number): Promise<StudentArtifactView> => {
    const response = await api.get<StudentArtifactView>(
      `/api/cmcp/artifacts/${encodeURIComponent(String(artifactId))}/student-view`,
    );
    return response.data;
  },
};
