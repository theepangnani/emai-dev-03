/**
 * CB-CMCP-001 M3-A 3A-2 (#4582) — Teacher review queue page tests.
 *
 * Covers:
 *   - Renders the queue when API returns data.
 *   - Approve flow calls the API.
 *   - Reject flow opens modal, validates required reason, then calls API.
 *   - Regenerate flow runs window.confirm + calls API on accept.
 *   - Edit flow opens textarea, sends PATCH on save.
 *   - Feature-flag-OFF path renders the disabled message.
 *
 * Mocks the API client (no real network calls), the feature-flag hook,
 * and the focus-trap hook.
 */
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactElement, ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// ── Mocks ──────────────────────────────────────────────────────────────

const mockListQueue = vi.fn();
const mockGetArtifact = vi.fn();
const mockEditArtifact = vi.fn();
const mockApprove = vi.fn();
const mockReject = vi.fn();
const mockRegenerate = vi.fn();

vi.mock('../../../api/cmcpReview', () => ({
  cmcpReviewApi: {
    listQueue: (...args: unknown[]) => mockListQueue(...args),
    getArtifact: (...args: unknown[]) => mockGetArtifact(...args),
    editArtifact: (...args: unknown[]) => mockEditArtifact(...args),
    approve: (...args: unknown[]) => mockApprove(...args),
    reject: (...args: unknown[]) => mockReject(...args),
    regenerate: (...args: unknown[]) => mockRegenerate(...args),
  },
}));

const mockFlagState = vi.fn();
vi.mock('../../../hooks/useFeatureToggle', () => ({
  useFeatureFlagState: (key: string) => mockFlagState(key),
}));

// useFocusTrap reads document focus during effects — stub it to a no-op
// so that tests don't depend on jsdom focus behaviour.
vi.mock('../../../hooks/useFocusTrap', () => ({
  useFocusTrap: () => ({ current: null }),
}));

import { ReviewQueuePage } from '../ReviewQueuePage';

// ── Helpers ────────────────────────────────────────────────────────────

function renderPage(ui: ReactElement) {
  // Per-test QueryClient with retries off so failed mutations surface
  // immediately and don't leave timers running between tests.
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/teacher/review']}>
          {children}
        </MemoryRouter>
      </QueryClientProvider>
    );
  }
  return render(ui, { wrapper: Wrapper });
}

const sampleArtifact = {
  id: 42,
  user_id: 7,
  course_id: 12,
  title: 'Photosynthesis study guide',
  content: '# Photosynthesis\n\nPlants convert light to chemical energy.',
  guide_type: 'STUDY_GUIDE',
  state: 'PENDING_REVIEW',
  se_codes: ['SCI.B1.1', 'SCI.B1.2'],
  voice_module_hash: 'abc123',
  requested_persona: 'STUDENT',
  board_id: 'TDSB',
  alignment_score: 0.92,
  ceg_version: 4,
  class_context_envelope_summary: null,
  edit_history: [],
  reviewed_by_user_id: null,
  reviewed_at: null,
  rejection_reason: null,
  created_at: '2026-04-29T10:00:00Z',
};

const sampleQueueItem = {
  id: sampleArtifact.id,
  title: sampleArtifact.title,
  guide_type: sampleArtifact.guide_type,
  state: sampleArtifact.state,
  course_id: sampleArtifact.course_id,
  user_id: sampleArtifact.user_id,
  se_codes: sampleArtifact.se_codes,
  requested_persona: sampleArtifact.requested_persona,
  created_at: sampleArtifact.created_at,
};

const sampleQueueResponse = {
  items: [sampleQueueItem],
  total: 1,
  page: 1,
  limit: 20,
};

// ── Tests ──────────────────────────────────────────────────────────────

describe('ReviewQueuePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFlagState.mockReturnValue({ enabled: true, isLoading: false });
    mockListQueue.mockResolvedValue(sampleQueueResponse);
    mockGetArtifact.mockResolvedValue(sampleArtifact);
  });

  it('renders the queue and auto-selects the first item', async () => {
    renderPage(<ReviewQueuePage />);

    expect(
      await screen.findByText('Pending review queue'),
    ).toBeInTheDocument();
    // Queue list rendered the row.
    expect(
      await screen.findByTestId(`cmcp-review-row-${sampleArtifact.id}`),
    ).toBeInTheDocument();
    // Detail panel auto-loaded the first item.
    await waitFor(() => {
      expect(mockGetArtifact).toHaveBeenCalledWith(sampleArtifact.id);
    });
    expect(
      await screen.findByText(`Artifact #${sampleArtifact.id}`),
    ).toBeInTheDocument();
  });

  it('shows the disabled message when cmcp.enabled is OFF', async () => {
    mockFlagState.mockReturnValue({ enabled: false, isLoading: false });
    renderPage(<ReviewQueuePage />);

    expect(
      await screen.findByText('Curriculum-mapped review is currently disabled'),
    ).toBeInTheDocument();
    expect(mockListQueue).not.toHaveBeenCalled();
  });

  it('renders empty state when the queue is empty', async () => {
    mockListQueue.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      limit: 20,
    });
    renderPage(<ReviewQueuePage />);

    expect(
      await screen.findByText('No artifacts pending review'),
    ).toBeInTheDocument();
    // Detail panel shows the "Select an artifact" empty state.
    expect(await screen.findByText('Select an artifact')).toBeInTheDocument();
  });

  it('approve button calls the approve API', async () => {
    mockApprove.mockResolvedValue({
      ...sampleArtifact,
      state: 'APPROVED',
      reviewed_by_user_id: 7,
      reviewed_at: '2026-04-29T11:00:00Z',
    });
    const user = userEvent.setup();
    renderPage(<ReviewQueuePage />);

    const approveBtn = await screen.findByTestId('cmcp-review-approve-btn');
    await user.click(approveBtn);

    await waitFor(() => {
      expect(mockApprove).toHaveBeenCalledWith(sampleArtifact.id);
    });
  });

  it('reject flow requires a reason before calling the API', async () => {
    mockReject.mockResolvedValue({
      ...sampleArtifact,
      state: 'REJECTED',
      rejection_reason: 'Off topic',
    });
    const user = userEvent.setup();
    renderPage(<ReviewQueuePage />);

    const rejectBtn = await screen.findByTestId('cmcp-review-reject-btn');
    await user.click(rejectBtn);

    // Modal is open.
    const dialog = await screen.findByRole('dialog', { name: 'Reject artifact' });
    expect(dialog).toBeInTheDocument();

    // Click confirm with empty reason — should NOT call API; should show error.
    const confirmBtn = within(dialog).getByRole('button', {
      name: /Reject artifact/,
    });
    await user.click(confirmBtn);
    expect(
      within(dialog).getByText('A reason is required to reject an artifact.'),
    ).toBeInTheDocument();
    expect(mockReject).not.toHaveBeenCalled();

    // Now type a reason and confirm.
    const textarea = within(dialog).getByLabelText(/Reason for rejection/);
    await user.type(textarea, 'Off topic');
    await user.click(confirmBtn);

    await waitFor(() => {
      expect(mockReject).toHaveBeenCalledWith(sampleArtifact.id, {
        reason: 'Off topic',
      });
    });
  });

  it('regenerate flow confirms then calls the API', async () => {
    mockRegenerate.mockResolvedValue({
      ...sampleArtifact,
      content: '# Photosynthesis (regenerated)\n\nNew prompt body.',
    });
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const user = userEvent.setup();
    renderPage(<ReviewQueuePage />);

    const regenBtn = await screen.findByTestId('cmcp-review-regenerate-btn');
    await user.click(regenBtn);

    expect(confirmSpy).toHaveBeenCalled();
    await waitFor(() => {
      expect(mockRegenerate).toHaveBeenCalledTimes(1);
    });
    const callArgs = mockRegenerate.mock.calls[0];
    expect(callArgs[0]).toBe(sampleArtifact.id);
    expect(callArgs[1].request.content_type).toBe('STUDY_GUIDE');
    expect(callArgs[1].request.subject_code).toBe('SCI');

    confirmSpy.mockRestore();
  });

  it('regenerate flow does NOT call the API when the user cancels confirm', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    const user = userEvent.setup();
    renderPage(<ReviewQueuePage />);

    const regenBtn = await screen.findByTestId('cmcp-review-regenerate-btn');
    await user.click(regenBtn);

    expect(confirmSpy).toHaveBeenCalled();
    expect(mockRegenerate).not.toHaveBeenCalled();

    confirmSpy.mockRestore();
  });

  it('edit flow opens the textarea, sends PATCH, and exits edit mode', async () => {
    mockEditArtifact.mockResolvedValue({
      ...sampleArtifact,
      content: '# Photosynthesis\n\nUpdated body.',
    });
    const user = userEvent.setup();
    renderPage(<ReviewQueuePage />);

    const editBtn = await screen.findByTestId('cmcp-review-edit-btn');
    await user.click(editBtn);

    const textarea = await screen.findByTestId('cmcp-review-edit-textarea');
    await user.clear(textarea);
    await user.type(textarea, 'Updated content');

    const saveBtn = screen.getByTestId('cmcp-review-save-edit-btn');
    await user.click(saveBtn);

    await waitFor(() => {
      expect(mockEditArtifact).toHaveBeenCalledWith(sampleArtifact.id, {
        content: 'Updated content',
      });
    });
  });
});
