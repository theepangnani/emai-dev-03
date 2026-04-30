/** CB-CMCP-001 M3-C 3C-4 (#4587) — CmcpLearningCard unit tests.
 *
 * Coverage:
 * - Renders the list of items returned by the mocked API client.
 * - Empty-state copy renders when the API returns no items.
 * - SELF_STUDY rows surface the SelfStudyBadge.
 * - parent_companion_available=true items navigate to the
 *   ``/parent/companion/:artifact_id`` route on click.
 * - parent_companion_available=false items remain non-clickable
 *   (M3α surface — generic detail route lands later).
 * - Loading + error states render the expected fallback copy.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor, fireEvent } from '@testing-library/react';
import { renderWithProviders } from '../../../test/helpers';
import { CmcpLearningCard } from '../CmcpLearningCard';

const mockList = vi.fn();
const mockNavigate = vi.fn();

vi.mock('../../../api/bridgeCmcpCard', async () => {
  const actual = await vi.importActual<typeof import('../../../api/bridgeCmcpCard')>(
    '../../../api/bridgeCmcpCard',
  );
  return {
    ...actual,
    bridgeCmcpCardApi: {
      list: (...args: unknown[]) => mockList(...args),
    },
  };
});

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>(
    'react-router-dom',
  );
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

beforeEach(() => {
  mockList.mockReset();
  mockNavigate.mockReset();
});

describe('CmcpLearningCard', () => {
  it('renders the card header copy with the kid name', async () => {
    mockList.mockResolvedValue({ items: [] });
    renderWithProviders(<CmcpLearningCard kidId={42} kidName="Aiden" />);
    expect(
      screen.getByText(/what aiden is learning/i),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(mockList).toHaveBeenCalledWith(42);
    });
  });

  it('renders the empty state when the API returns no items', async () => {
    mockList.mockResolvedValue({ items: [] });
    renderWithProviders(<CmcpLearningCard kidId={42} kidName="Aiden" />);
    await waitFor(() => {
      expect(
        screen.getByText(/no recent learning to review for aiden yet\./i),
      ).toBeInTheDocument();
    });
  });

  it('renders rows from the API and routes APPROVED + parent-companion-available items to the parent companion page', async () => {
    mockList.mockResolvedValue({
      items: [
        {
          artifact_id: 11,
          content_type: 'study_guide',
          subject: 'Math',
          topic: 'Cell Division',
          state: 'APPROVED',
          created_at: '2026-04-29T10:00:00+00:00',
          parent_companion_available: true,
        },
        {
          artifact_id: 12,
          content_type: 'quiz',
          subject: 'Science',
          topic: 'Photosynthesis quiz',
          state: 'APPROVED',
          created_at: '2026-04-29T09:00:00+00:00',
          parent_companion_available: false,
        },
      ],
    });
    renderWithProviders(<CmcpLearningCard kidId={7} kidName="Maya" />);
    await waitFor(() => {
      expect(screen.getByText('Cell Division')).toBeInTheDocument();
    });
    expect(screen.getByText('Photosynthesis quiz')).toBeInTheDocument();
    expect(screen.getByText('Math')).toBeInTheDocument();
    expect(screen.getByText('Science')).toBeInTheDocument();

    // Clicking the parent-companion-available item navigates.
    const clickable = screen.getByTestId('bridge-cmcp-item-11');
    fireEvent.click(clickable);
    expect(mockNavigate).toHaveBeenCalledWith('/parent/companion/11');

    // Clicking the unavailable item is a no-op (no navigate call beyond the first).
    const nonClickable = screen.getByTestId('bridge-cmcp-item-12');
    fireEvent.click(nonClickable);
    expect(mockNavigate).toHaveBeenCalledTimes(1);
  });

  it('renders the SelfStudyBadge for SELF_STUDY rows', async () => {
    mockList.mockResolvedValue({
      items: [
        {
          artifact_id: 21,
          content_type: 'study_guide',
          subject: 'English',
          topic: 'Persuasive essays',
          state: 'SELF_STUDY',
          created_at: '2026-04-29T08:00:00+00:00',
          parent_companion_available: false,
        },
      ],
    });
    renderWithProviders(<CmcpLearningCard kidId={9} kidName="Sam" />);
    await waitFor(() => {
      expect(screen.getByText('Persuasive essays')).toBeInTheDocument();
    });
    expect(screen.getByTestId('cmcp-self-study-badge')).toBeInTheDocument();
  });

  it('renders the loading state before the query resolves', async () => {
    let resolve!: (value: { items: never[] }) => void;
    mockList.mockReturnValue(
      new Promise<{ items: never[] }>((res) => {
        resolve = res;
      }),
    );
    renderWithProviders(<CmcpLearningCard kidId={1} kidName="Lee" />);
    expect(
      screen.getByText(/loading recent learning…/i),
    ).toBeInTheDocument();
    resolve({ items: [] });
    await waitFor(() => {
      expect(
        screen.queryByText(/loading recent learning…/i),
      ).not.toBeInTheDocument();
    });
  });

  it('renders an error fallback when the API rejects', async () => {
    mockList.mockRejectedValue(new Error('boom'));
    renderWithProviders(<CmcpLearningCard kidId={1} kidName="Lee" />);
    await waitFor(() => {
      expect(
        screen.getByText(
          /couldn’t load recent learning right now\. try again in a moment\./i,
        ),
      ).toBeInTheDocument();
    });
  });

  it('renders a placeholder dash when subject is null', async () => {
    mockList.mockResolvedValue({
      items: [
        {
          artifact_id: 33,
          content_type: 'worksheet',
          subject: null,
          topic: 'Mixed practice',
          state: 'APPROVED',
          created_at: '2026-04-29T07:00:00+00:00',
          parent_companion_available: false,
        },
      ],
    });
    renderWithProviders(<CmcpLearningCard kidId={5} kidName="Theo" />);
    await waitFor(() => {
      expect(screen.getByText('Mixed practice')).toBeInTheDocument();
    });
    expect(screen.getByText('—')).toBeInTheDocument();
  });
});
