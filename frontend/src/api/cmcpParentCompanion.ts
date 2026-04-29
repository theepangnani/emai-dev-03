// TODO(M3, #4531): Endpoint requires content_artifacts persistence which lands in M3. Page is gated until then.
/**
 * CB-CMCP-001 M1-F 1F-4 (#4498) — Parent Companion artifact API client.
 *
 * Thin wrapper around `GET /api/cmcp/artifacts/{artifact_id}/parent-companion`.
 * The endpoint returns the 5-section ``ParentCompanionContent`` produced by
 * 1F-2 ``ParentCompanionService.generate_5_section()``. The shape mirrors the
 * Pydantic model in ``app/services/cmcp/parent_companion_service.py``.
 *
 * GATING (M1 followup #4531): The backend GET endpoint does NOT exist in M1.
 * M1 ships parent_companion content inline on the SSE generation/stream
 * completion event only. The fetch-by-artifact-id pattern requires M3's
 * `content_artifacts` table writes. Until M3 lands, the corresponding
 * `<Route path="/parent/companion/:artifact_id">` registration is commented
 * out in `App.tsx`, so this client and `ParentCompanionPage` are not
 * reachable from the running app. They are kept in tree (and unit-tested
 * with mocks) to minimize churn when M3 wires the GET endpoint.
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

export const cmcpParentCompanionApi = {
  /**
   * Fetch the Parent Companion 5-section content for a given artifact id.
   * Throws (axios error) on 401/403/404; the page component catches and
   * renders the error state.
   */
  get: async (artifactId: string | number): Promise<ParentCompanionContent> => {
    const response = await api.get(
      `/api/cmcp/artifacts/${encodeURIComponent(String(artifactId))}/parent-companion`,
    );
    return response.data as ParentCompanionContent;
  },
};
