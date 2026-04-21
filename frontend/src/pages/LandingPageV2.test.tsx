/**
 * LandingPageV2 scaffold tests (CB-LAND-001 S2 / #3802).
 *
 * Keeps the surface area tiny: the page's job in S2 is to mount, stamp
 * `data-landing="v2"` so S1 tokens activate, and render the sorted
 * section registry (or an empty-state notice). Section-specific tests
 * ship with each S3-S12 stripe.
 */
import { describe, it, expect } from 'vitest';
import { renderWithProviders } from '../test/helpers';
import { LandingPageV2 } from './LandingPageV2';

describe('LandingPageV2 (scaffold)', () => {
  it('renders the landing-v2 root with data-landing="v2" when the section list is empty', () => {
    const { container } = renderWithProviders(
      <LandingPageV2 sections={[]} />,
    );

    const root = container.querySelector('main[data-landing="v2"]');
    expect(root).not.toBeNull();
    expect(root?.getAttribute('data-landing')).toBe('v2');
    // Empty-state notice is present so the route is never a blank page.
    expect(container.querySelector('[data-testid="landing-v2-empty"]')).not.toBeNull();
  });
});
