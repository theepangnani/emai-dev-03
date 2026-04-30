/**
 * CB-CMCP-001 M3-A 3A-2 (#4582) — Teacher review queue page.
 *
 * Route: /teacher/review
 * RBAC: TEACHER + ADMIN (gated by `<ProtectedRoute>` in App.tsx).
 *
 * Two-pane layout:
 *   - Left:  paginated PENDING_REVIEW queue (`ReviewQueueList`).
 *   - Right: full artifact detail + actions (`ArtifactDetailPanel`).
 *
 * Backend endpoints consumed (shipped 3A-1 / PR #4608):
 *   GET    /api/cmcp/review/queue
 *   GET    /api/cmcp/review/{id}
 *   PATCH  /api/cmcp/review/{id}
 *   POST   /api/cmcp/review/{id}/approve
 *   POST   /api/cmcp/review/{id}/reject
 *   POST   /api/cmcp/review/{id}/regenerate
 *
 * Out of scope (deferred to siblings):
 *   - SE-tag editor (3A-3 / #4583): slot in ArtifactDetailPanel.
 *   - Regenerate UX modal (3A-4 / #4584): currently a basic confirm.
 */
import { useEffect, useState } from 'react';
import { useFeatureFlagState } from '../../hooks/useFeatureToggle';
import {
  useApproveArtifact,
  useEditArtifact,
  useRegenerateArtifact,
  useRejectArtifact,
  useReviewArtifact,
  useReviewQueue,
} from '../../hooks/useCmcpReview';
import type { ReviewSortField } from '../../api/cmcpReview';
import { ReviewQueueList } from './ReviewQueueList';
import { ArtifactDetailPanel } from './ArtifactDetailPanel';
import { RejectReasonModal } from './RejectReasonModal';
import './ReviewQueuePage.css';

const PAGE_LIMIT = 20;

function errorMessage(err: unknown): string | null {
  if (!err) return null;
  if (err instanceof Error) {
    // Axios errors expose a server-shaped detail under err.response.data.detail.
    const maybe = (err as { response?: { data?: { detail?: unknown } } })
      .response?.data?.detail;
    if (typeof maybe === 'string') return maybe;
    return err.message || 'Request failed.';
  }
  return null;
}

export function ReviewQueuePage() {
  const { enabled: cmcpEnabled, isLoading: flagLoading } =
    useFeatureFlagState('cmcp.enabled');

  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState<ReviewSortField>('created_at');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [showRejectModal, setShowRejectModal] = useState(false);

  const queueQuery = useReviewQueue(
    { page, limit: PAGE_LIMIT, sort_by: sortBy },
    { enabled: cmcpEnabled },
  );

  const detailQuery = useReviewArtifact(
    cmcpEnabled ? selectedId : null,
  );

  const editMutation = useEditArtifact();
  const approveMutation = useApproveArtifact();
  const rejectMutation = useRejectArtifact();
  const regenerateMutation = useRegenerateArtifact();

  // Auto-select the first item once the queue resolves so the right
  // pane isn't empty on initial render. Re-runs only when the items
  // identity changes (page change, sort change, or queue refetch
  // bringing in a new top row).
  const items = queueQuery.data?.items ?? [];
  const firstItemId = items[0]?.id ?? null;
  useEffect(() => {
    if (selectedId !== null) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: auto-select first row once the queue query resolves, so the right pane isn't empty on first render
    if (firstItemId !== null) setSelectedId(firstItemId);
  }, [firstItemId, selectedId]);

  // ── Feature-flag OFF / hydrating ────────────────────────────────────
  if (flagLoading) {
    return (
      <div className="cmcp-review-page" data-testid="cmcp-review-page">
        <p className="cmcp-review-state-msg">Loading…</p>
      </div>
    );
  }

  if (!cmcpEnabled) {
    return (
      <div className="cmcp-review-page" data-testid="cmcp-review-page">
        <div className="cmcp-review-disabled" role="status">
          <h2>Curriculum-mapped review is currently disabled</h2>
          <p>Contact an admin to enable the CB-CMCP-001 feature flag.</p>
        </div>
      </div>
    );
  }

  // ── Action handlers ─────────────────────────────────────────────────
  const handleApprove = () => {
    if (selectedId === null || approveMutation.isPending) return;
    approveMutation.mutate(selectedId);
  };

  const handleConfirmReject = (reason: string) => {
    if (selectedId === null) return;
    rejectMutation.mutate(
      { artifactId: selectedId, payload: { reason } },
      {
        onSuccess: () => {
          setShowRejectModal(false);
        },
      },
    );
  };

  const handleSaveEdit = (content: string) => {
    if (selectedId === null) return;
    editMutation.mutate({
      artifactId: selectedId,
      payload: { content },
    });
  };

  /**
   * Basic regenerate confirm + call. The full UX (#4584 / 3A-4) will
   * land a parameter-edit modal; until then we re-run the prompt build
   * with the artifact's current grade/subject/strand/persona/content_type
   * snapshot. Backend wraps the inner CMCPGenerateRequest, so we need to
   * re-derive the original generation parameters — but those aren't
   * persisted on study_guides. For 3A-2 we surface a confirm + a clear
   * message that the regenerate-with-params modal is coming next.
   */
  const handleRegenerate = () => {
    if (!detailQuery.data || regenerateMutation.isPending) return;
    const proceed = window.confirm(
      'Regenerate this artifact with the current parameters?\n\n' +
        '(The full regenerate UX with editable parameters ships in stripe ' +
        '3A-4 / issue #4584. For now this re-runs with the artifact’s ' +
        'existing SE codes + persona.)',
    );
    if (!proceed) return;
    const artifact = detailQuery.data;
    const subject = artifact.se_codes[0]?.split('.')[0] ?? '';
    if (!subject) {
      window.alert(
        'Cannot regenerate: the artifact has no SE codes to derive a subject from. ' +
          'Edit the SE codes first (coming in 3A-3 / #4583).',
      );
      return;
    }
    regenerateMutation.mutate({
      artifactId: artifact.id,
      payload: {
        request: {
          // Grade is not persisted on study_guides — backend defaults from
          // user/course context. Send a placeholder of 1; 3A-4 will surface
          // the full param form.
          grade: 1,
          subject_code: subject,
          content_type: artifact.guide_type,
          target_persona: artifact.requested_persona ?? null,
          course_id: artifact.course_id,
        },
      },
    });
  };

  const selectedTitle = detailQuery.data?.title ?? `#${selectedId ?? ''}`;

  return (
    <div className="cmcp-review-page" data-testid="cmcp-review-page">
      <header className="cmcp-review-page-header">
        <div>
          <div className="cmcp-review-kicker">
            CB-CMCP-001 / Teacher review
          </div>
          <h1 className="cmcp-review-title">Pending review queue</h1>
        </div>
        <p className="cmcp-review-page-subtitle">
          Review CMCP-generated artifacts before they reach students or
          parents. Approve to publish, reject with a reason, or regenerate
          to try a different prompt.
        </p>
      </header>

      <div className="cmcp-review-layout">
        <ReviewQueueList
          items={items}
          total={queueQuery.data?.total ?? 0}
          page={page}
          limit={PAGE_LIMIT}
          sortBy={sortBy}
          isLoading={queueQuery.isLoading}
          isFetching={queueQuery.isFetching}
          error={queueQuery.error}
          selectedId={selectedId}
          onSelect={(id) => setSelectedId(id)}
          onSortChange={(s) => {
            setSortBy(s);
            setPage(1);
            setSelectedId(null);
          }}
          onPageChange={(p) => {
            setPage(p);
            setSelectedId(null);
          }}
        />

        <ArtifactDetailPanel
          artifact={detailQuery.data ?? null}
          isLoading={selectedId !== null && detailQuery.isLoading}
          error={detailQuery.error ?? null}
          isEditing={editMutation.isPending}
          isApproving={approveMutation.isPending}
          isRejecting={rejectMutation.isPending}
          isRegenerating={regenerateMutation.isPending}
          editError={errorMessage(editMutation.error)}
          approveError={errorMessage(approveMutation.error)}
          regenerateError={errorMessage(regenerateMutation.error)}
          onSaveEdit={handleSaveEdit}
          onApprove={handleApprove}
          onRequestReject={() => setShowRejectModal(true)}
          onRegenerate={handleRegenerate}
        />
      </div>

      <RejectReasonModal
        open={showRejectModal}
        artifactTitle={selectedTitle}
        isSubmitting={rejectMutation.isPending}
        errorMessage={errorMessage(rejectMutation.error)}
        onCancel={() => {
          if (!rejectMutation.isPending) {
            setShowRejectModal(false);
            rejectMutation.reset();
          }
        }}
        onConfirm={handleConfirmReject}
      />
    </div>
  );
}
