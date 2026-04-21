/**
 * LandingPageV2 scaffold tests (CB-LAND-001 S2 / #3802).
 *
 * Keeps the surface area tiny: the page's job in S2 is to mount, stamp
 * `data-landing="v2"` so S1 tokens activate, and render the sorted
 * section registry (or an empty-state notice). Section-specific tests
 * ship with each S3-S12 stripe.
 *
 * #3873 — also verifies the landing-v2 Google Fonts stylesheet is
 * injected on mount and removed on unmount so non-landing routes don't
 * pay its render-blocking cost. Hook-level ref-counting is covered in
 * `../components/landing/fonts.test.tsx`.
 */
import { describe, it, expect, afterEach } from 'vitest';
import { renderWithProviders } from '../test/helpers';
import { LandingPageV2 } from './LandingPageV2';

describe('LandingPageV2 (scaffold)', () => {
  afterEach(() => {
    // Defensive cleanup: any stale landing-fonts <link> from a prior test
    // in the same jsdom document is removed so each test starts clean.
    document.head
      .querySelectorAll('link[data-landing-fonts]')
      .forEach((el) => el.remove());
  });

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

  it('injects the landing-v2 Google Fonts stylesheet on mount and removes it on unmount (#3873)', () => {
    const { unmount } = renderWithProviders(<LandingPageV2 sections={[]} />);

    const link = document.head.querySelector<HTMLLinkElement>(
      'link[data-landing-fonts]',
    );
    expect(link).not.toBeNull();
    expect(link?.rel).toBe('stylesheet');
    expect(link?.href).toContain('fonts.googleapis.com/css2');
    expect(link?.href).toContain('Fraunces');
    expect(link?.href).toContain('Instrument+Sans');

    unmount();

    expect(
      document.head.querySelector('link[data-landing-fonts]'),
    ).toBeNull();
  });
});
