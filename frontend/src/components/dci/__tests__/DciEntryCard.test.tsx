import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
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
    expect(
      screen.getByRole('button', { name: /open today.*summary/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /kid view/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/share this link with your kid/i),
    ).toBeInTheDocument();
  });

  it('renders nothing when dci_v1_enabled is OFF', () => {
    mockUseFeatureFlagState.mockReturnValue({ enabled: false, isLoading: false });

    const { container } = renderWithProviders(<DciEntryCard />);

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
