/**
 * CB-DCI-001 (#4266) — kid-friendly needs-consent page tests.
 *
 * Verifies the page renders the explanatory copy and the copy-link
 * affordance writes the consent URL to the clipboard.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { renderWithProviders } from '../../../test/helpers';
import { CheckinNeedsConsentPage } from '../CheckinNeedsConsentPage';

describe('CheckinNeedsConsentPage (#4266)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the kid-friendly explanation', () => {
    renderWithProviders(<CheckinNeedsConsentPage />);
    // The heading uses a typographic right-single-quote (&rsquo;) so we match
    // on the unique fragments around it instead of the apostrophe itself.
    expect(
      screen.getByRole('heading', { name: /need your parent.+OK first/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Show this page to your parent/i),
    ).toBeInTheDocument();
  });

  it('shows the consent URL on screen', () => {
    renderWithProviders(<CheckinNeedsConsentPage />);
    const link = screen.getByTestId('dci-needs-consent-url');
    expect(link.textContent).toContain('/dci/consent');
  });

  it('shows "Copied!" feedback after the copy button is clicked', async () => {
    // jsdom doesn't ship `document.execCommand`, and `navigator.clipboard`
    // permissions aren't granted by default. Stub both so the handler's
    // success path runs and the button flips to "Copied!".
    const writeText = vi.fn().mockResolvedValue(undefined);
    const originalDescriptor = Object.getOwnPropertyDescriptor(
      window.navigator,
      'clipboard',
    );
    Object.defineProperty(window.navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
    });
    // execCommand is missing on jsdom — attach a stub so the optional
    // fallback path still works if clipboard isn't picked up.
    (document as Document & { execCommand?: (cmd: string) => boolean }).execCommand =
      vi.fn(() => true);

    try {
      const user = userEvent.setup();
      renderWithProviders(<CheckinNeedsConsentPage />);

      await user.click(screen.getByTestId('dci-needs-consent-copy'));

      // What matters is the user sees the "Copied!" affordance flip on.
      expect(
        await screen.findByRole('button', { name: /copied/i }),
      ).toBeInTheDocument();
    } finally {
      if (originalDescriptor) {
        Object.defineProperty(window.navigator, 'clipboard', originalDescriptor);
      } else {
        delete (window.navigator as Navigator & { clipboard?: unknown }).clipboard;
      }
    }
  });
});
