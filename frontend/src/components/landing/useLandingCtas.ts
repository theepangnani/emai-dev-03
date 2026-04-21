/**
 * useLandingCtas — branches landing-page secondary CTAs + pricing copy
 * based on the `waitlist_enabled` feature toggle (regression guard for #1219,
 * originally surfaced as #3889 on LandingPageV2).
 *
 * When waitlist is ON (default pre-launch posture): CTAs route to `/waitlist`
 * and say "Join the waitlist". When waitlist is OFF (launch mode): CTAs route
 * to `/register` and say "Get Started". PricingTeaser also adapts its
 * free-tier framing.
 *
 * Mirrors the pattern used by the legacy `LaunchLandingPage` (via
 * `useFeature('waitlist_enabled')`) so both landing pages share a single
 * source of truth for the admin toggle.
 */
import { useFeature } from '../../hooks/useFeatureToggle';

export type LandingPricingMode = 'waitlist' | 'launch';

export interface LandingCtas {
  /**
   * Long-form CTA label — used by hero / final CTA / pricing copy where
   * horizontal space allows a full sentence ("Join the waitlist").
   */
  secondaryLabel: string;
  /**
   * Short-form CTA label — used by the top nav where the button sits in a
   * compact actions row ("Join Waitlist"). In launch mode both forms
   * collapse to the same "Get Started" string.
   */
  secondaryLabelShort: string;
  secondaryHref: string;
  pricingMode: LandingPricingMode;
  waitlistEnabled: boolean;
}

export function useLandingCtas(): LandingCtas {
  const waitlistEnabled = useFeature('waitlist_enabled');
  return waitlistEnabled
    ? {
        secondaryLabel: 'Join the waitlist',
        secondaryLabelShort: 'Join Waitlist',
        secondaryHref: '/waitlist',
        pricingMode: 'waitlist',
        waitlistEnabled: true,
      }
    : {
        secondaryLabel: 'Get Started',
        secondaryLabelShort: 'Get Started',
        secondaryHref: '/register',
        pricingMode: 'launch',
        waitlistEnabled: false,
      };
}
