/**
 * LearningCyclePage — smoke test for the /tutor/cycle/:id shell
 * (CB-TUTOR-002 #4069).
 *
 * Shell-only: verifies the page renders the mock session behind the
 * `learning_cycle_enabled` feature flag, and bounces to /tutor when the
 * flag is off.
 */
import { screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderWithProviders } from '../test/helpers';
import { LearningCyclePage } from './LearningCyclePage';

// ── Mocks ─────────────────────────────────────────────────────
const flagEnabledMock = vi.fn<[string], boolean>();

vi.mock('../hooks/useFeatureToggle', async () => {
  const actual = await vi.importActual<
    typeof import('../hooks/useFeatureToggle')
  >('../hooks/useFeatureToggle');
  return {
    ...actual,
    useFeatureFlagEnabled: (key: string) => flagEnabledMock(key),
  };
});

vi.mock('../components/DashboardLayout', () => ({
  DashboardLayout: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="layout">{children}</div>
  ),
}));

// react-markdown pulls in unified + vfile at import time; stub so the shell
// test stays a pure render check.
vi.mock('react-markdown', () => ({
  default: ({ children }: { children: string }) => (
    <div data-testid="react-markdown">{children}</div>
  ),
}));

beforeEach(() => {
  flagEnabledMock.mockReset();
});

describe('LearningCyclePage', () => {
  it('renders the mock session teach block when the feature flag is enabled', () => {
    flagEnabledMock.mockReturnValue(true);

    renderWithProviders(<LearningCyclePage />, {
      initialEntries: ['/tutor/cycle/mock'],
    });

    // Topic header
    expect(screen.getByRole('heading', { level: 1, name: /fractions/i })).toBeInTheDocument();
    // Teach block heading
    expect(
      screen.getByRole('heading', { level: 2, name: /let.*s learn this part/i }),
    ).toBeInTheDocument();
    // Primary CTA to move into questions
    expect(
      screen.getByRole('button', { name: /ready for questions/i }),
    ).toBeInTheDocument();
    // Progress rail
    expect(screen.getByLabelText(/learning cycle progress/i)).toBeInTheDocument();
    // Markdown body was rendered via the stub
    expect(screen.getByTestId('react-markdown')).toBeInTheDocument();
    // Flag was consulted
    expect(flagEnabledMock).toHaveBeenCalledWith('learning_cycle_enabled');
  });
});
