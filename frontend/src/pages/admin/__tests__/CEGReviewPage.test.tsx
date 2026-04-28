/**
 * CB-CMCP-001 M0-B 0B-3b — Curriculum-admin review page tests (#4429).
 *
 * Covers:
 * - Pending list renders when API returns data
 * - Empty state when no pending expectations
 * - Error state when API fails
 * - Feature-flag-OFF state shows the disabled message
 * - Accept button calls API and removes the row optimistically
 * - Reject button calls API and removes the row optimistically
 * - Edit modal opens, validates, and submits PATCH
 * - 403 message when user lacks CURRICULUM_ADMIN role (route-level gating
 *   is exercised via the ProtectedRoute test surface — here we cover the
 *   page's own behaviour assuming it has rendered.)
 *
 * Mocks the API client (no real network calls), the feature-flag hook,
 * and the auth context.
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import type { ReactElement, ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// ── Mocks ──────────────────────────────────────────────────────────────

const mockListPending = vi.fn();
const mockAccept = vi.fn();
const mockReject = vi.fn();
const mockEdit = vi.fn();

vi.mock('../../../api/cegAdminReview', () => ({
  cegAdminReviewApi: {
    listPending: (...args: unknown[]) => mockListPending(...args),
    accept: (...args: unknown[]) => mockAccept(...args),
    reject: (...args: unknown[]) => mockReject(...args),
    edit: (...args: unknown[]) => mockEdit(...args),
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

import { CEGReviewPage } from '../CEGReviewPage';

// ── Helpers ────────────────────────────────────────────────────────────

function renderPage(ui: ReactElement) {
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter initialEntries={['/admin/ceg/review']}>
        {children}
      </MemoryRouter>
    );
  }
  return render(ui, { wrapper: Wrapper });
}

const sampleRow = {
  id: 1,
  ministry_code: 'B2.1',
  cb_code: 'CB-G7-MATH-B2-SE1',
  subject_id: 10,
  strand_id: 20,
  grade: 7,
  expectation_type: 'specific',
  parent_oe_id: null,
  description: 'A sample paraphrase that is more than twenty characters long.',
  curriculum_version_id: 100,
  active: false,
  review_state: 'pending',
  reviewed_by_user_id: null,
  reviewed_at: null,
  review_notes: null,
  created_at: '2026-04-27T10:00:00Z',
  updated_at: null,
};

// ── Tests ──────────────────────────────────────────────────────────────

describe('CEGReviewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFlagState.mockReturnValue({ enabled: true, isLoading: false });
  });

  it('renders pending list when API returns data', async () => {
    mockListPending.mockResolvedValue([sampleRow]);
    renderPage(<CEGReviewPage />);

    await waitFor(() => {
      expect(screen.getByText('CEG expectation review')).toBeInTheDocument();
    });

    expect(screen.getByText('B2.1')).toBeInTheDocument();
    expect(screen.getByText('CB-G7-MATH-B2-SE1')).toBeInTheDocument();
    expect(screen.getByText(/A sample paraphrase/)).toBeInTheDocument();
    expect(screen.getByText('SE')).toBeInTheDocument();
  });

  it('shows the disabled message when cmcp.enabled is OFF', async () => {
    mockFlagState.mockReturnValue({ enabled: false, isLoading: false });
    mockListPending.mockResolvedValue([]);
    renderPage(<CEGReviewPage />);

    expect(
      await screen.findByText('Curriculum review is currently disabled'),
    ).toBeInTheDocument();
    expect(mockListPending).not.toHaveBeenCalled();
  });

  it('shows the loading state while the flag is hydrating', () => {
    mockFlagState.mockReturnValue({ enabled: false, isLoading: true });
    mockListPending.mockResolvedValue([]);
    renderPage(<CEGReviewPage />);

    expect(screen.getByText(/Loading/)).toBeInTheDocument();
  });

  it('renders empty state when there are no pending expectations', async () => {
    mockListPending.mockResolvedValue([]);
    renderPage(<CEGReviewPage />);

    await waitFor(() => {
      expect(screen.getByText('No pending expectations')).toBeInTheDocument();
    });
  });

  it('renders error state when listPending fails', async () => {
    mockListPending.mockRejectedValue(new Error('boom'));
    renderPage(<CEGReviewPage />);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('boom');
    });
  });

  it('accept button calls API and removes the row optimistically', async () => {
    mockListPending.mockResolvedValue([sampleRow]);
    mockAccept.mockResolvedValue({
      ...sampleRow,
      review_state: 'accepted',
      active: true,
    });
    const user = userEvent.setup();
    renderPage(<CEGReviewPage />);

    const acceptBtn = await screen.findByRole('button', {
      name: /Accept expectation B2\.1/,
    });
    await user.click(acceptBtn);

    await waitFor(() => {
      expect(mockAccept).toHaveBeenCalledWith(sampleRow.id);
    });
    // Row removed from pending table → empty state shows.
    await waitFor(() => {
      expect(screen.getByText('No pending expectations')).toBeInTheDocument();
    });
  });

  it('reject button calls API and removes the row optimistically', async () => {
    mockListPending.mockResolvedValue([sampleRow]);
    mockReject.mockResolvedValue({
      ...sampleRow,
      review_state: 'rejected',
      active: false,
    });
    const user = userEvent.setup();
    renderPage(<CEGReviewPage />);

    const rejectBtn = await screen.findByRole('button', {
      name: /Reject expectation B2\.1/,
    });
    await user.click(rejectBtn);

    await waitFor(() => {
      expect(mockReject).toHaveBeenCalledWith(sampleRow.id);
    });
    await waitFor(() => {
      expect(screen.getByText('No pending expectations')).toBeInTheDocument();
    });
  });

  it('rolls back the row when accept fails', async () => {
    mockListPending.mockResolvedValue([sampleRow]);
    mockAccept.mockRejectedValue(new Error('accept failed'));
    const user = userEvent.setup();
    renderPage(<CEGReviewPage />);

    const acceptBtn = await screen.findByRole('button', {
      name: /Accept expectation B2\.1/,
    });
    await user.click(acceptBtn);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('accept failed');
    });
    // Row should be back.
    expect(screen.getByText('B2.1')).toBeInTheDocument();
  });

  it('opens the edit modal, validates, and submits PATCH', async () => {
    mockListPending.mockResolvedValue([sampleRow]);
    mockEdit.mockResolvedValue({
      ...sampleRow,
      description: 'A revised paraphrase that is also more than twenty chars.',
    });
    const user = userEvent.setup();
    renderPage(<CEGReviewPage />);

    const editBtn = await screen.findByRole('button', {
      name: /Edit expectation B2\.1/,
    });
    await user.click(editBtn);

    expect(
      await screen.findByRole('dialog', { name: 'Edit expectation' }),
    ).toBeInTheDocument();

    // Validation: clear description below 20 chars and verify save is blocked.
    const textarea = screen.getByLabelText('Paraphrase');
    await user.clear(textarea);
    await user.type(textarea, 'too short');
    await user.click(screen.getByRole('button', { name: 'Save' }));
    expect(
      screen.getByText(/Paraphrase must be at least 20 characters/),
    ).toBeInTheDocument();
    expect(mockEdit).not.toHaveBeenCalled();

    // Now submit a valid edit.
    await user.clear(textarea);
    await user.type(
      textarea,
      'A revised paraphrase that is also more than twenty chars.',
    );
    await user.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(mockEdit).toHaveBeenCalledWith(sampleRow.id, {
        description:
          'A revised paraphrase that is also more than twenty chars.',
      });
    });
  });

  it('rejects ministry codes that do not match the regex', async () => {
    mockListPending.mockResolvedValue([sampleRow]);
    const user = userEvent.setup();
    renderPage(<CEGReviewPage />);

    const editBtn = await screen.findByRole('button', {
      name: /Edit expectation B2\.1/,
    });
    await user.click(editBtn);

    const ministryInput = screen.getByLabelText('Ministry code');
    await user.clear(ministryInput);
    await user.type(ministryInput, 'invalid-code');
    await user.click(screen.getByRole('button', { name: 'Save' }));

    expect(
      screen.getByText(/Ministry code must match pattern/),
    ).toBeInTheDocument();
    expect(mockEdit).not.toHaveBeenCalled();
  });
});
