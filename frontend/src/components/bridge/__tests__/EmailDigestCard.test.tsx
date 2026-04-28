/** #4349 Stream M — EmailDigestCard embed coverage.
 *
 * Verifies the new `showRecentHistory` prop renders the
 * DigestHistoryPanel below the footer when an integration exists,
 * and stays hidden otherwise (back-compat with existing callers).
 *
 * #4399 (Stream J) — also verifies the `description` prop is forwarded
 * only in single-kid mode (`aggregate=false`).
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

  // S-6: description prop wiring
  it('passes description hint to DigestHistoryPanel in single-kid mode (aggregate=false)', async () => {
    renderWithProviders(
      <EmailDigestCard
        {...baseProps}
        aggregate={false}
        childName="Aiden"
        showRecentHistory
      />,
    );
    await waitFor(() => {
      expect(
        screen.getByText('These digests cover all your kids.'),
      ).toBeInTheDocument();
    });
  });

  it('omits description in all-kids mode (aggregate=true)', async () => {
    const { container } = renderWithProviders(
      <EmailDigestCard {...baseProps} aggregate showRecentHistory />,
    );
    // Wait for panel to render so we know the absence is real (not a timing race).
    await waitFor(() => {
      expect(screen.getByText(/digest history/i)).toBeInTheDocument();
    });
    expect(
      screen.queryByText('These digests cover all your kids.'),
    ).not.toBeInTheDocument();
    expect(container.querySelector('.dhp-description')).toBeNull();
  });
});
