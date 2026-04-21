import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithRouter } from '../../../test/helpers';

// Mock useFeature so we can exercise both waitlist-on and waitlist-off
// branches of `useLandingCtas` (#3889). Hero itself imports only
// `useLandingCtas`, but the hook reaches into `useFeatureToggle`.
const useFeatureMock = vi.fn<(key: string) => boolean>();
vi.mock('../../../hooks/useFeatureToggle', () => ({
  useFeature: (key: string) => useFeatureMock(key),
}));

import { LandingHero } from './LandingHero';

describe('LandingHero', () => {
  beforeEach(() => {
    useFeatureMock.mockReset();
    // Default: waitlist ON (pre-launch posture).
    useFeatureMock.mockReturnValue(true);
  });

  it('renders headline, both CTAs, and all five trust-bar chips', () => {
    renderWithRouter(<LandingHero />);

    // Headline — verifies the <h1> text and the serif <em> accent both mount.
    const heading = screen.getByRole('heading', { level: 1 });
    expect(heading.textContent).toContain('homework gap');
    expect(heading.querySelector('em')).not.toBeNull();

    // Primary CTA — opens the InstantTrialModal (state lifted inside component).
    expect(
      screen.getByRole('button', { name: /try the 30-second demo/i }),
    ).toBeInTheDocument();

    // Secondary CTA — router <Link> to /waitlist.
    const waitlistLink = screen.getByRole('link', { name: /join the waitlist/i });
    expect(waitlistLink).toBeInTheDocument();
    expect(waitlistLink.getAttribute('href')).toBe('/waitlist');

    // Trust bar — kicker + 5 board chips.
    expect(screen.getByText(/trusted by ontario school boards/i)).toBeInTheDocument();
    const list = screen.getByRole('list', { name: /ontario school boards/i });
    expect(list.querySelectorAll('li')).toHaveLength(5);
    for (const name of ['YRDSB', 'TDSB', 'DDSB', 'PDSB', 'OCDSB']) {
      expect(screen.getByText(name)).toBeInTheDocument();
    }
  });

  it('routes secondary CTA to /register with "Get Started" label when waitlist_enabled is false (#3889)', () => {
    useFeatureMock.mockReturnValue(false);
    renderWithRouter(<LandingHero />);

    // No waitlist link should exist in launch mode.
    expect(
      screen.queryByRole('link', { name: /join the waitlist/i }),
    ).not.toBeInTheDocument();

    const registerLink = screen.getByRole('link', { name: /get started/i });
    expect(registerLink.getAttribute('href')).toBe('/register');
  });
});
