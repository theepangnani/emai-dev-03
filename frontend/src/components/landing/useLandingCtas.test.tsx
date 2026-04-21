/**
 * useLandingCtas — #3889 regression guard.
 *
 * Asserts the hook returns the correct shape in both `waitlist_enabled`
 * states: waitlist-ON ⇒ `/waitlist` + "Join the waitlist" + pricingMode
 * 'waitlist'; waitlist-OFF ⇒ `/register` + "Get Started" + pricingMode
 * 'launch'.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useLandingCtas } from './useLandingCtas';

const useFeatureMock = vi.fn<(key: string) => boolean>();

vi.mock('../../hooks/useFeatureToggle', () => ({
  useFeature: (key: string) => useFeatureMock(key),
}));

describe('useLandingCtas', () => {
  beforeEach(() => {
    useFeatureMock.mockReset();
  });

  it('returns waitlist-mode shape when waitlist_enabled is true', () => {
    useFeatureMock.mockReturnValue(true);
    const { result } = renderHook(() => useLandingCtas());
    expect(result.current).toEqual({
      secondaryLabel: 'Join the waitlist',
      secondaryHref: '/waitlist',
      pricingMode: 'waitlist',
      waitlistEnabled: true,
    });
    expect(useFeatureMock).toHaveBeenCalledWith('waitlist_enabled');
  });

  it('returns launch-mode shape when waitlist_enabled is false', () => {
    useFeatureMock.mockReturnValue(false);
    const { result } = renderHook(() => useLandingCtas());
    expect(result.current).toEqual({
      secondaryLabel: 'Get Started',
      secondaryHref: '/register',
      pricingMode: 'launch',
      waitlistEnabled: false,
    });
    expect(useFeatureMock).toHaveBeenCalledWith('waitlist_enabled');
  });

  it('returns waitlist-mode shape while the feature-toggle query is pending (#3895)', () => {
    // `useFeature` defaults `waitlist_enabled` to true during hydration so
    // the hook should produce the waitlist-mode CTAs, not "Get Started".
    useFeatureMock.mockReturnValue(true);
    const { result } = renderHook(() => useLandingCtas());
    expect(result.current.secondaryLabel).toBe('Join the waitlist');
    expect(result.current.secondaryHref).toBe('/waitlist');
    expect(result.current.pricingMode).toBe('waitlist');
    expect(result.current.waitlistEnabled).toBe(true);
  });
});
