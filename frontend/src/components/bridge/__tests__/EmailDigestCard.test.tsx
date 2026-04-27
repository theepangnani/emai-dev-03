/** #4349 Stream M — EmailDigestCard embed coverage.
 *
 * Verifies the new `showRecentHistory` prop renders the
 * DigestHistoryPanel below the footer when an integration exists,
 * and stays hidden otherwise (back-compat with existing callers).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../../test/helpers';
import { EmailDigestCard } from '../EmailDigestCard';

const mockGetLogs = vi.fn();

vi.mock('../../../api/parentEmailDigest', async () => {
  const actual = await vi.importActual<typeof import('../../../api/parentEmailDigest')>(
    '../../../api/parentEmailDigest',
  );
  return {
    ...actual,
    getLogs: (...args: unknown[]) => mockGetLogs(...args),
  };
});

beforeEach(() => {
  mockGetLogs.mockReset();
  mockGetLogs.mockResolvedValue({ data: [] });
});

const baseProps = {
  hasIntegration: true,
  onSetup: vi.fn(),
  onOpenDigest: vi.fn(),
};

describe('EmailDigestCard — showRecentHistory', () => {
  it('does not render DigestHistoryPanel by default (back-compat)', () => {
    renderWithProviders(<EmailDigestCard {...baseProps} aggregate />);
    expect(screen.queryByText(/digest history/i)).not.toBeInTheDocument();
    expect(mockGetLogs).not.toHaveBeenCalled();
  });

  it('renders DigestHistoryPanel when showRecentHistory + hasIntegration', async () => {
    renderWithProviders(
      <EmailDigestCard {...baseProps} aggregate showRecentHistory />,
    );
    // Heading from the embedded panel
    expect(screen.getByText(/digest history/i)).toBeInTheDocument();
    // The panel queries logs with limit=5
    await waitFor(() => {
      expect(mockGetLogs).toHaveBeenCalledWith({ limit: 5 });
    });
  });

  it('does NOT render DigestHistoryPanel when showRecentHistory but no integration', () => {
    renderWithProviders(
      <EmailDigestCard
        {...baseProps}
        hasIntegration={false}
        aggregate
        showRecentHistory
      />,
    );
    expect(screen.queryByText(/digest history/i)).not.toBeInTheDocument();
    expect(mockGetLogs).not.toHaveBeenCalled();
  });

  it('renders the "Open daily digest →" button when an integration exists', () => {
    renderWithProviders(<EmailDigestCard {...baseProps} aggregate showRecentHistory />);
    expect(screen.getByRole('button', { name: /open daily digest/i })).toBeInTheDocument();
  });
});
