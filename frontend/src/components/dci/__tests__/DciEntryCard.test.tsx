import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../../test/helpers';
import { DciEntryCard } from '../DciEntryCard';

const mockUseFeatureFlagState = vi.fn<
  (key: string) => { enabled: boolean; isLoading: boolean }
>();

vi.mock('../../../hooks/useFeatureToggle', async () => {
  const actual = await vi.importActual<
    typeof import('../../../hooks/useFeatureToggle')
  >('../../../hooks/useFeatureToggle');
  return {
    ...actual,
    useFeatureFlagState: (key: string) => mockUseFeatureFlagState(key),
  };
});

beforeEach(() => {
  vi.clearAllMocks();
});

describe('DciEntryCard (#4258)', () => {
  it('renders the entry card when dci_v1_enabled is ON', () => {
    mockUseFeatureFlagState.mockReturnValue({ enabled: true, isLoading: false });

    renderWithProviders(<DciEntryCard />);

    expect(mockUseFeatureFlagState).toHaveBeenCalledWith('dci_v1_enabled');
    expect(
      screen.getByRole('heading', { level: 3, name: /daily check-in/i }),
    ).toBeInTheDocument();
    // Primary + secondary actions are now <Link role="button"> for native
    // open-in-new-tab semantics (#4264).
    const primary = screen.getByRole('button', { name: /open today.*summary/i });
    const secondary = screen.getByRole('button', { name: /kid view/i });
    expect(primary).toBeInTheDocument();
    expect(primary).toHaveAttribute('href', '/parent/today');
    expect(secondary).toBeInTheDocument();
    expect(secondary).toHaveAttribute('href', '/checkin');
    expect(
      screen.getByRole('button', { name: /copy link/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/share this link with your kid/i),
    ).toBeInTheDocument();
  });

  it('copies the kid view URL to the clipboard when Copy link is clicked', async () => {
    mockUseFeatureFlagState.mockReturnValue({ enabled: true, isLoading: false });
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
      writable: true,
    });

    renderWithProviders(<DciEntryCard />);

    fireEvent.click(screen.getByRole('button', { name: /copy link/i }));

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(
        `${window.location.origin}/checkin`,
      );
    });
    expect(
      await screen.findByRole('button', { name: /copied!/i }),
    ).toBeInTheDocument();
  });

  it('renders nothing when dci_v1_enabled is OFF', () => {
    mockUseFeatureFlagState.mockReturnValue({ enabled: false, isLoading: false });

    const { container } = renderWithProviders(<DciEntryCard />);

    // Hardening (#4264): assert the OFF-case queries the correct flag key,
    // matching the ON-case assertion above.
    expect(mockUseFeatureFlagState).toHaveBeenCalledWith('dci_v1_enabled');
    expect(container).toBeEmptyDOMElement();
    expect(
      screen.queryByRole('heading', { name: /daily check-in/i }),
    ).not.toBeInTheDocument();
  });

  it('renders nothing while the flag query is loading', () => {
    mockUseFeatureFlagState.mockReturnValue({ enabled: false, isLoading: true });

    const { container } = renderWithProviders(<DciEntryCard />);

    expect(container).toBeEmptyDOMElement();
  });
});
