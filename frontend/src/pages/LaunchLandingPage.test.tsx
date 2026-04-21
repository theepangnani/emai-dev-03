/**
 * LaunchLandingPage — #3895 hydration flicker regression guard.
 *
 * Asserts that when `useFeature('waitlist_enabled')` is still hydrating
 * (returns `true` per the per-key load default), the legacy landing page
 * renders the "Join the Waitlist" primary CTA and does NOT render
 * "Get Started". Once #3895 regresses, `useFeature` would return `false`
 * during hydration and this test would surface the flicker.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../test/helpers';

const useFeatureMock = vi.fn<(key: string) => boolean>();
const useVariantBucketMock = vi.fn<(key: string) => 'on' | 'off'>();

vi.mock('../hooks/useFeatureToggle', () => ({
  useFeature: (key: string) => useFeatureMock(key),
}));

vi.mock('../hooks/useVariantBucket', () => ({
  useVariantBucket: (key: string) => useVariantBucketMock(key),
}));

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: null }),
}));

// Heavy demo sections are unrelated to the CTA under test; stub them so we
// don't need to wire their own providers just to render the hero.
vi.mock('../components/demo/TuesdayMirror', () => ({
  TuesdayMirror: () => null,
}));
vi.mock('../components/demo/InstantTrialSection', () => ({
  InstantTrialSection: () => null,
}));
vi.mock('../components/demo/InstantTrialModal', () => ({
  InstantTrialModal: () => null,
}));
vi.mock('../components/demo/RoleSwitcher', () => ({
  default: () => null,
}));
vi.mock('../components/demo/ProofWall', () => ({
  ProofWall: () => null,
}));

import { LaunchLandingPage } from './LaunchLandingPage';

describe('LaunchLandingPage (#3895 hydration flicker)', () => {
  beforeEach(() => {
    useFeatureMock.mockReset();
    useVariantBucketMock.mockReset();
    useVariantBucketMock.mockReturnValue('off');
  });

  it('renders the waitlist CTA (not "Get Started") while the feature query is pending', () => {
    // `useFeature` defaults `waitlist_enabled` to true during hydration,
    // so the hero primary CTA should read "Join the Waitlist".
    useFeatureMock.mockImplementation((key) =>
      key === 'waitlist_enabled' ? true : false,
    );

    renderWithProviders(<LaunchLandingPage />);

    expect(
      screen.getByRole('link', { name: /join the waitlist/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('link', { name: /^get started$/i }),
    ).not.toBeInTheDocument();
  });

  it('renders "Get Started" only when waitlist_enabled resolves to false', () => {
    useFeatureMock.mockReturnValue(false);

    renderWithProviders(<LaunchLandingPage />);

    expect(
      screen.getByRole('link', { name: /^get started$/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('link', { name: /join the waitlist/i }),
    ).not.toBeInTheDocument();
  });
});
