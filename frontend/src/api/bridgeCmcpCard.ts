/**
 * CB-CMCP-001 M3-C 3C-4 (#4587) — Bridge "What [child] is learning" card API client.
 *
 * Thin wrapper around `GET /api/bridge/cards/cmcp/{kid_id}` (defined in
 * ``app/api/routes/bridge_cmcp.py``).
 *
 * The endpoint surfaces APPROVED + SELF_STUDY CMCP artifacts for a single
 * linked child. The backend handles the visibility check (PARENT must be
 * linked to ``kid_id`` via ``parent_students``); cross-family calls 404.
 */
import { api } from './client';

export type CmcpArtifactState = 'APPROVED' | 'SELF_STUDY' | string;

export interface BridgeCmcpCardItem {
  artifact_id: number;
  content_type: string;
  subject: string | null;
  topic: string;
  state: CmcpArtifactState;
  created_at: string | null;
  parent_companion_available: boolean;
}

export interface BridgeCmcpCardResponse {
  items: BridgeCmcpCardItem[];
}

export const bridgeCmcpCardApi = {
  /**
   * Fetch up to 5 (default) recent CMCP artifacts visible on the
   * Bridge "What [child] is learning" card. The backend caps ``limit``
   * at 20.
   */
  list: async (
    kidId: number,
    limit: number = 5,
  ): Promise<BridgeCmcpCardResponse> => {
    const response = await api.get<BridgeCmcpCardResponse>(
      `/api/bridge/cards/cmcp/${encodeURIComponent(String(kidId))}`,
      { params: { limit } },
    );
    return response.data;
  },
};
