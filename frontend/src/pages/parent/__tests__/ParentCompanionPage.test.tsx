/**
 * CB-CMCP-001 M1-F 1F-4 (#4498) — vitest tests for ParentCompanionPage.
 *
 * Covers:
 *   - Loading state on initial mount.
 *   - Ready state renders all 5 sections (header + 4 content sections + CTA).
 *   - Error state with axios-shape errors (404 / 403 / generic).
 *   - Empty state when the API returns blank content.
 *   - Bridge deep-link CTA disabled when no `deep_link_target`.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../../test/helpers';
import { ParentCompanionPage } from '../ParentCompanionPage';
import type { ParentCompanionContent } from '../../../api/cmcpParentCompanion';

const mockGet = vi.fn();

vi.mock('../../../api/cmcpParentCompanion', () => ({
  cmcpParentCompanionApi: {
    get: (...args: unknown[]) => mockGet(...args),
  },
}));

// Stub DashboardLayout so the test stays focused on the page body.
vi.mock('../../../components/DashboardLayout', () => ({
  DashboardLayout: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="dashboard-layout">{children}</div>
  ),
}));

// Pin useParams to a known artifact id for every test below. Individual
// tests override mockGet's resolved value to drive each branch.
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>(
    'react-router-dom',
  );
  return {
    ...actual,
    useParams: () => ({ artifact_id: 'art-123' }),
  };
});

function makeContent(
  overrides: Partial<ParentCompanionContent> = {},
): ParentCompanionContent {
  return {
    se_explanation:
      'Your child is exploring how plants make their own food. This week focuses on the basics of photosynthesis.',
    talking_points: [
      'Ask what plants need to grow.',
      'Talk about where energy comes from.',
      'Notice plants on the walk home.',
    ],
    coaching_prompts: [
      'What surprised you in class today?',
      'How would you explain it to a younger sibling?',
    ],
    how_to_help_without_giving_answer:
      'Ask questions instead of giving answers. If they get stuck, prompt them to look back at their notes.',
    bridge_deep_link_payload: {
      child_id: 42,
      week_summary: 'Week of Apr 27',
      deep_link_target: '/bridge/child/42',
    },
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('ParentCompanionPage', () => {
  it('shows the loading state on first render', () => {
    // never-resolving promise so we stay in `loading`
    mockGet.mockReturnValue(new Promise<ParentCompanionContent>(() => {}));
    renderWithProviders(<ParentCompanionPage />);
    expect(screen.getByTestId('parent-companion-loading')).toBeInTheDocument();
  });

  it('renders all five Parent Companion sections when content is ready', async () => {
    mockGet.mockResolvedValue(makeContent());
    renderWithProviders(<ParentCompanionPage />);

    // Wait for the explanation section (first content block) to mount —
    // confirms the loading state has resolved.
    await waitFor(() =>
      expect(screen.getByTestId('parent-companion-explanation')).toBeInTheDocument(),
    );

    // Page header (1 of 5 visual blocks the issue calls out — kicker + title)
    expect(screen.getByTestId('parent-companion-header')).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: /how to support your child this week/i }),
    ).toBeInTheDocument();

    // Section 1 — SE explanation
    expect(
      screen.getByText(/your child is exploring how plants make their own food/i),
    ).toBeInTheDocument();

    // Section 2 — Talking points (3 items)
    const talking = screen.getByTestId('parent-companion-talking-points');
    expect(talking).toBeInTheDocument();
    expect(talking.querySelectorAll('li')).toHaveLength(3);
    expect(talking).toHaveTextContent('Ask what plants need to grow.');

    // Section 3 — Coaching prompts (2 items)
    const prompts = screen.getByTestId('parent-companion-prompts');
    expect(prompts).toBeInTheDocument();
    expect(prompts.querySelectorAll('li')).toHaveLength(2);
    expect(prompts).toHaveTextContent('What surprised you in class today?');

    // Section 4 — How to help without giving the answer
    const howTo = screen.getByTestId('parent-companion-how-to-help');
    expect(howTo).toBeInTheDocument();
    expect(howTo).toHaveTextContent(/ask questions instead of giving answers/i);

    // Section 5 — Bridge deep link CTA
    const cta = screen.getByTestId('parent-companion-deeplink');
    expect(cta).toBeInTheDocument();
    expect(cta).toHaveTextContent('Week of Apr 27');
    const link = screen.getByTestId('parent-companion-deeplink-link');
    expect(link).toHaveAttribute('href', '/bridge/child/42');
  });

  it('hides talking-points + coaching-prompts sections when arrays are empty', async () => {
    mockGet.mockResolvedValue(
      makeContent({ talking_points: [], coaching_prompts: [] }),
    );
    renderWithProviders(<ParentCompanionPage />);

    await waitFor(() =>
      expect(screen.getByTestId('parent-companion-explanation')).toBeInTheDocument(),
    );
    expect(screen.queryByTestId('parent-companion-talking-points')).toBeNull();
    expect(screen.queryByTestId('parent-companion-prompts')).toBeNull();
    // Section 4 + CTA still render — they don't depend on those arrays.
    expect(screen.getByTestId('parent-companion-how-to-help')).toBeInTheDocument();
    expect(screen.getByTestId('parent-companion-deeplink')).toBeInTheDocument();
  });

  it('disables the deep-link CTA when no deep_link_target is provided', async () => {
    mockGet.mockResolvedValue(
      makeContent({
        bridge_deep_link_payload: {
          child_id: 42,
          week_summary: 'Week of Apr 27',
          deep_link_target: null,
        },
      }),
    );
    renderWithProviders(<ParentCompanionPage />);

    await waitFor(() =>
      expect(screen.getByTestId('parent-companion-deeplink')).toBeInTheDocument(),
    );
    expect(screen.queryByTestId('parent-companion-deeplink-link')).toBeNull();
    const fallback = screen.getByTestId('parent-companion-deeplink-disabled');
    expect(fallback).toBeDisabled();
  });

  it('renders the empty state when the API returns blank content', async () => {
    mockGet.mockResolvedValue(
      makeContent({
        se_explanation: '   ',
        talking_points: [],
        coaching_prompts: [],
        how_to_help_without_giving_answer: '',
      }),
    );
    renderWithProviders(<ParentCompanionPage />);

    await waitFor(() =>
      expect(screen.getByTestId('parent-companion-empty')).toBeInTheDocument(),
    );
    expect(screen.queryByTestId('parent-companion-explanation')).toBeNull();
  });

  it('renders the 404 error state when the artifact is not found', async () => {
    mockGet.mockRejectedValue({
      response: { status: 404, data: { detail: 'Not found' } },
      message: 'Request failed with status code 404',
    });
    renderWithProviders(<ParentCompanionPage />);

    await waitFor(() =>
      expect(screen.getByTestId('parent-companion-error')).toBeInTheDocument(),
    );
    expect(
      screen.getByRole('heading', { name: /companion not found/i }),
    ).toBeInTheDocument();
  });

  it('renders the 403 error state when the user does not own the artifact', async () => {
    mockGet.mockRejectedValue({
      response: { status: 403, data: { detail: 'Forbidden' } },
    });
    renderWithProviders(<ParentCompanionPage />);

    await waitFor(() =>
      expect(screen.getByTestId('parent-companion-error')).toBeInTheDocument(),
    );
    expect(
      screen.getByRole('heading', { name: /you don't have access/i }),
    ).toBeInTheDocument();
  });

  it('renders a generic error state for unexpected failures', async () => {
    mockGet.mockRejectedValue(new Error('Network down'));
    renderWithProviders(<ParentCompanionPage />);

    await waitFor(() =>
      expect(screen.getByTestId('parent-companion-error')).toBeInTheDocument(),
    );
    expect(
      screen.getByRole('heading', { name: /something went wrong/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/network down/i)).toBeInTheDocument();
  });
});
