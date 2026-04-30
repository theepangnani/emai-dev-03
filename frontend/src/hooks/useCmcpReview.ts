/**
 * CB-CMCP-001 M3-A 3A-2 (#4582) — TanStack Query hooks for the teacher
 * review queue.
 *
 * Wraps `cmcpReviewApi` (`frontend/src/api/cmcpReview.ts`) with the
 * dev-03 query/mutation conventions:
 *   - Stable query keys under `['cmcp-review', ...]` for invalidation.
 *   - Mutations invalidate the queue + per-artifact detail caches on
 *     success so the UI reflects the new server state without manual
 *     refetch wiring at the page layer.
 */
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryResult,
  type UseMutationResult,
} from '@tanstack/react-query';
import {
  cmcpReviewApi,
  type EditDeltaPayload,
  type QueueListParams,
  type RegeneratePayload,
  type RejectPayload,
  type ReviewArtifactDetail,
  type ReviewQueueResponse,
} from '../api/cmcpReview';

const REVIEW_KEY_ROOT = 'cmcp-review';

export const cmcpReviewKeys = {
  all: [REVIEW_KEY_ROOT] as const,
  queue: (params: QueueListParams) =>
    [REVIEW_KEY_ROOT, 'queue', params] as const,
  detail: (artifactId: number) =>
    [REVIEW_KEY_ROOT, 'detail', artifactId] as const,
};

/** GET /api/cmcp/review/queue — paginated PENDING_REVIEW list. */
export function useReviewQueue(
  params: QueueListParams = {},
  options: { enabled?: boolean } = {},
): UseQueryResult<ReviewQueueResponse, Error> {
  return useQuery<ReviewQueueResponse, Error>({
    queryKey: cmcpReviewKeys.queue(params),
    queryFn: () => cmcpReviewApi.listQueue(params),
    enabled: options.enabled ?? true,
  });
}

/** GET /api/cmcp/review/{id} — full artifact + metadata. */
export function useReviewArtifact(
  artifactId: number | null,
): UseQueryResult<ReviewArtifactDetail, Error> {
  return useQuery<ReviewArtifactDetail, Error>({
    queryKey:
      artifactId === null
        ? [REVIEW_KEY_ROOT, 'detail', 'idle']
        : cmcpReviewKeys.detail(artifactId),
    queryFn: () => cmcpReviewApi.getArtifact(artifactId as number),
    enabled: artifactId !== null,
  });
}

interface EditMutationVars {
  artifactId: number;
  payload: EditDeltaPayload;
}

/** PATCH /api/cmcp/review/{id} — inline content edit. */
export function useEditArtifact(): UseMutationResult<
  ReviewArtifactDetail,
  Error,
  EditMutationVars
> {
  const qc = useQueryClient();
  return useMutation<ReviewArtifactDetail, Error, EditMutationVars>({
    mutationFn: ({ artifactId, payload }) =>
      cmcpReviewApi.editArtifact(artifactId, payload),
    onSuccess: (updated) => {
      qc.setQueryData(cmcpReviewKeys.detail(updated.id), updated);
      qc.invalidateQueries({ queryKey: [REVIEW_KEY_ROOT, 'queue'] });
    },
  });
}

/** POST /api/cmcp/review/{id}/approve. */
export function useApproveArtifact(): UseMutationResult<
  ReviewArtifactDetail,
  Error,
  number
> {
  const qc = useQueryClient();
  return useMutation<ReviewArtifactDetail, Error, number>({
    mutationFn: (artifactId: number) => cmcpReviewApi.approve(artifactId),
    onSuccess: (updated) => {
      qc.setQueryData(cmcpReviewKeys.detail(updated.id), updated);
      qc.invalidateQueries({ queryKey: [REVIEW_KEY_ROOT, 'queue'] });
    },
  });
}

interface RejectMutationVars {
  artifactId: number;
  payload: RejectPayload;
}

/** POST /api/cmcp/review/{id}/reject — `reason` required. */
export function useRejectArtifact(): UseMutationResult<
  ReviewArtifactDetail,
  Error,
  RejectMutationVars
> {
  const qc = useQueryClient();
  return useMutation<ReviewArtifactDetail, Error, RejectMutationVars>({
    mutationFn: ({ artifactId, payload }) =>
      cmcpReviewApi.reject(artifactId, payload),
    onSuccess: (updated) => {
      qc.setQueryData(cmcpReviewKeys.detail(updated.id), updated);
      qc.invalidateQueries({ queryKey: [REVIEW_KEY_ROOT, 'queue'] });
    },
  });
}

interface RegenerateMutationVars {
  artifactId: number;
  payload: RegeneratePayload;
}

/** POST /api/cmcp/review/{id}/regenerate — re-run prompt build. */
export function useRegenerateArtifact(): UseMutationResult<
  ReviewArtifactDetail,
  Error,
  RegenerateMutationVars
> {
  const qc = useQueryClient();
  return useMutation<ReviewArtifactDetail, Error, RegenerateMutationVars>({
    mutationFn: ({ artifactId, payload }) =>
      cmcpReviewApi.regenerate(artifactId, payload),
    onSuccess: (updated) => {
      qc.setQueryData(cmcpReviewKeys.detail(updated.id), updated);
      qc.invalidateQueries({ queryKey: [REVIEW_KEY_ROOT, 'queue'] });
    },
  });
}
