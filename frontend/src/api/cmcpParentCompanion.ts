/**
 * CB-CMCP-001 M1-F 1F-4 (#4498) — Parent Companion artifact API client.
 *
 * Thin wrapper around `GET /api/cmcp/artifacts/{artifact_id}/parent-companion`.
 * The endpoint returns the 5-section ``ParentCompanionContent`` produced by
 * 1F-2 ``ParentCompanionService.generate_5_section()``. The shape mirrors the
 * Pydantic model in ``app/services/cmcp/parent_companion_service.py``.
 *
 * M3α prequel (#4575) wired the backend endpoint, so this client is now live.
 * The endpoint returns ``{ artifact_id, content }`` where ``content`` matches
 * the 5-section ``ParentCompanionContent`` schema below; this client unwraps
 * to the inner ``content`` so existing call-sites keep their existing shape.
 */
import { api } from './client';

export interface BridgeDeepLinkPayload {
  child_id?: number | string | null;
  week_summary?: string | null;
  deep_link_target?: string | null;
}

export interface ParentCompanionContent {
  se_explanation: string;
  talking_points: string[];
  coaching_prompts: string[];
  how_to_help_without_giving_answer: string;
  bridge_deep_link_payload: BridgeDeepLinkPayload;
}

interface ParentCompanionArtifactResponse {
  artifact_id: number;
  content: ParentCompanionContent;
}

export const cmcpParentCompanionApi = {
  /**
   * Fetch the Parent Companion 5-section content for a given artifact id.
   * Throws (axios error) on 401/403/404/422; the page component catches and
   * renders the error state.
   */
  get: async (artifactId: string | number): Promise<ParentCompanionContent> => {
    const response = await api.get<ParentCompanionArtifactResponse>(
      `/api/cmcp/artifacts/${encodeURIComponent(String(artifactId))}/parent-companion`,
    );
    return response.data.content;
  },
};
