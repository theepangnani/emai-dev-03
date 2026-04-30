/**
 * CB-CMCP-001 M3-H 3H-1 (#4663) — Board catalog API client.
 *
 * Typed Axios wrapper for the 3E-1 (PR #4671) endpoint:
 *
 *   GET /api/board/{board_id}/catalog
 *
 * Auth/visibility (enforced server-side):
 *   - BOARD_ADMIN of own board OR ADMIN.
 *   - Cross-board reads by a BOARD_ADMIN return 404 (no existence oracle).
 *   - Other roles → 403; unauth → 401; `cmcp.enabled` flag OFF → 403.
 *
 * Response shape mirrors `BoardCatalogResponse` /
 * `BoardCatalogArtifact` Pydantic schemas exactly. The strand × grade
 * coverage map for the heatmap UI (3H-1) is derived on the client from
 * `se_codes[0]` — Ontario SE codes are namespaced
 * `<SUBJECT>.<GRADE>.<STRAND>.<...>` and 3E-2's `coverage_map_service`
 * uses the same parse on the backend.
 */
import { api } from './client';

export interface BoardCatalogArtifact {
  id: number;
  title: string;
  content_type: string;
  state: string;
  subject_code: string | null;
  grade: number | null;
  se_codes: string[];
  alignment_score: number | null;
  ai_engine: string | null;
  course_id: number | null;
  created_at: string | null;
}

export interface BoardCatalogResponse {
  artifacts: BoardCatalogArtifact[];
  next_cursor: string | null;
}

export interface BoardCatalogParams {
  cursor?: string | null;
  limit?: number;
  subject_code?: string | null;
  grade?: number | null;
  content_type?: string | null;
}

export const boardCatalogApi = {
  /** Paginated APPROVED-artifact list scoped to one board. */
  async getCatalog(
    boardId: string,
    params: BoardCatalogParams = {},
  ): Promise<BoardCatalogResponse> {
    const { data } = await api.get<BoardCatalogResponse>(
      `/api/board/${encodeURIComponent(boardId)}/catalog`,
      { params },
    );
    return data;
  },
};
