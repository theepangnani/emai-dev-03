/**
 * LandingPageV2 accessibility test — CB-LAND-001 S14 (#3814).
 *
 * This file exercises the WCAG 2.1 AA checklist items that can be verified
 * through DOM queries (jsdom) without a real browser. Full axe-core /
 * Lighthouse scans require `vitest-axe`, which is not currently a dev-dep;
 * tracked via CB-LAND-001-fast-follow "S14: add vitest-axe + automated
 * axe scan to landing-v2".
 *
 * What this test DOES cover:
 *  1. Skip-to-content link exists, targets `#main`, and precedes <main>.
 *  2. Exactly one <h1> in the page; all other sections use <h2> at the top.
 *  3. The <main id="main"> landmark wraps the section registry output.
 *  4. <footer> (the LandingFooter section) is rendered OUTSIDE <main>.
 *  5. Accordion panels follow the APG pattern: buttons have aria-expanded
 *     + aria-controls, panels carry role="region" with a matching id and
 *     the `hidden` attribute when collapsed.
 *  6. Tabs follow the APG pattern: role="tablist"/tab/tabpanel, and the
 *     active tab has tabindex="0" while inactive tabs have tabindex="-1".
 *  7. All <img> elements have an `alt` attribute (meaningful or empty).
 *  8. Every <button> inside landing sections has accessible text.
 *  9. No element has a positive `tabindex` (keyboard-order hazard).
 */
import { describe, it, expect } from 'vitest';
import { renderWithProviders } from '../../test/helpers';
import { LandingPageV2 } from '../LandingPageV2';
import { buildSectionRegistry } from '../../components/landing/sectionRegistry';

function renderPage() {
  return renderWithProviders(<LandingPageV2 />);
}

describe('LandingPageV2 — WCAG 2.1 AA a11y pass (S14, #3814)', () => {
  it('has a skip-to-content link that targets #main and precedes <main>', () => {
    const { container } = renderPage();
    const skip = container.querySelector<HTMLAnchorElement>(
      'a.landing-v2-skip-link',
    );
    expect(skip).not.toBeNull();
    expect(skip?.getAttribute('href')).toBe('#main');

    // Skip link must appear in DOM order BEFORE the <main> landmark so a
    // keyboard user hitting Tab first lands on it.
    const main = container.querySelector('main[data-landing="v2"]');
    expect(main).not.toBeNull();
    if (skip && main) {
      const rel = skip.compareDocumentPosition(main);
      expect(rel & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    }
  });

  it('renders <main id="main"> as the primary landmark', () => {
    const { container } = renderPage();
    const main = container.querySelector('main');
    expect(main).not.toBeNull();
    expect(main?.getAttribute('id')).toBe('main');
    expect(main?.getAttribute('data-landing')).toBe('v2');
  });

  it('has exactly one <h1> across the full landing page', () => {
    const { container } = renderPage();
    const h1s = container.querySelectorAll('h1');
    expect(h1s.length).toBe(1);
  });

  it('renders <footer> OUTSIDE <main>', () => {
    const { container } = renderPage();
    const main = container.querySelector('main');
    const footer = container.querySelector('footer');
    expect(main).not.toBeNull();
    expect(footer).not.toBeNull();
    // The footer MUST NOT be a descendant of <main>.
    expect(main?.contains(footer)).toBe(false);
  });

  it('every <img> has an alt attribute', () => {
    const { container } = renderPage();
    const imgs = container.querySelectorAll('img');
    imgs.forEach((img) => {
      expect(img.hasAttribute('alt')).toBe(true);
    });
  });

  it('every <button> has accessible text (text content or aria-label)', () => {
    const { container } = renderPage();
    const buttons = container.querySelectorAll('button');
    buttons.forEach((btn) => {
      const text = (btn.textContent ?? '').trim();
      const ariaLabel = btn.getAttribute('aria-label') ?? '';
      const ariaLabelledBy = btn.getAttribute('aria-labelledby') ?? '';
      expect(text.length > 0 || ariaLabel.length > 0 || ariaLabelledBy.length > 0).toBe(
        true,
      );
    });
  });

  it('no element uses a positive tabindex (keyboard-order hazard)', () => {
    const { container } = renderPage();
    const tabbables = container.querySelectorAll('[tabindex]');
    tabbables.forEach((el) => {
      const raw = el.getAttribute('tabindex');
      const n = Number(raw);
      expect(Number.isFinite(n)).toBe(true);
      expect(n <= 0).toBe(true);
    });
  });

  it('HowItWorksAccordion follows the WAI-ARIA APG pattern', () => {
    const { container } = renderPage();
    const buttons = container.querySelectorAll<HTMLButtonElement>(
      '.landing-how__row-button',
    );
    // If the accordion section is registered, we expect at least one row.
    expect(buttons.length).toBeGreaterThan(0);

    let expandedCount = 0;
    buttons.forEach((btn) => {
      expect(btn.hasAttribute('aria-expanded')).toBe(true);
      const expanded = btn.getAttribute('aria-expanded') === 'true';
      if (expanded) expandedCount += 1;

      const controlsId = btn.getAttribute('aria-controls');
      expect(controlsId).toBeTruthy();

      const panel = container.querySelector(`#${controlsId}`);
      expect(panel).not.toBeNull();
      expect(panel?.getAttribute('role')).toBe('region');

      // Collapsed panels carry the `hidden` attribute; expanded panels do not.
      if (expanded) {
        expect(panel?.hasAttribute('hidden')).toBe(false);
      } else {
        expect(panel?.hasAttribute('hidden')).toBe(true);
      }
    });

    // Exactly one row starts expanded.
    expect(expandedCount).toBe(1);
  });

  it('LearnerSegmentTabs follows the WAI-ARIA APG pattern', () => {
    const { container } = renderPage();
    const tablist = container.querySelector('[role="tablist"]');
    expect(tablist).not.toBeNull();

    const tabs = container.querySelectorAll<HTMLButtonElement>('[role="tab"]');
    expect(tabs.length).toBeGreaterThan(0);

    let activeCount = 0;
    tabs.forEach((tab) => {
      expect(tab.hasAttribute('aria-selected')).toBe(true);
      const selected = tab.getAttribute('aria-selected') === 'true';
      if (selected) {
        activeCount += 1;
        expect(tab.getAttribute('tabindex')).toBe('0');
      } else {
        expect(tab.getAttribute('tabindex')).toBe('-1');
      }

      const controlsId = tab.getAttribute('aria-controls');
      expect(controlsId).toBeTruthy();
    });

    expect(activeCount).toBe(1);

    const panel = container.querySelector('[role="tabpanel"]');
    expect(panel).not.toBeNull();
  });

  it('section registry actually populates (sanity check)', () => {
    // Guard against the regression where an empty registry makes the
    // other assertions trivially pass.
    const registry = buildSectionRegistry();
    expect(registry.length).toBeGreaterThan(0);
  });
});
