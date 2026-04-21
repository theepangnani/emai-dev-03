/**
 * LandingPageV2 — page-level integration tests (CB-LAND-001 S17, #3817).
 *
 * The scaffold test at `../LandingPageV2.test.tsx` covers the empty-registry
 * case. This file covers the page as a composed unit:
 *
 *   1. Flag-on render            — all 11 registered sections mount in order
 *   2. Flag-off render           — legacy LaunchLandingPage renders
 *   3. Demo CTA smoke            — hero CTA mounts InstantTrialModal (mocked)
 *   4. Reduced-motion            — ComparisonSplit renders without bounce
 *   5. Registry ordering         — section orders are ascending 10..9999
 *   6. Keyboard focus order      — hero CTA first, footer link last, no
 *                                  positive tabIndex values
 *
 * Section-level content/behavior stays with each section's own unit test —
 * this file deliberately avoids duplicating those assertions.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../../test/helpers';

// ─── Module mocks ───────────────────────────────────────────────────────
// InstantTrialModal is mounted by LandingHero on primary-CTA click. We mock
// it so the test asserts *mount* without pulling in its API surface.
vi.mock('../../components/demo/InstantTrialModal', () => ({
  InstantTrialModal: ({ onClose }: { onClose: () => void }) => (
    <div data-testid="instant-trial-modal-mock" role="dialog">
      <button type="button" onClick={onClose}>
        close-mock
      </button>
    </div>
  ),
}));

// LaunchLandingPage reaches useAuth + useFeatureToggle. Both are stubbed so
// the flag-off render test can mount it without the full provider stack.
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ user: null }),
}));
vi.mock('../../hooks/useFeatureToggle', () => ({
  useFeatureToggles: () => ({
    google_classroom: false,
    waitlist_enabled: false,
    _variants: {},
  }),
  useFeature: () => false,
  useFeatureVariant: () => 'off',
}));

// useVariantBucket is mocked so flag-on / flag-off branches are deterministic
// when we render pages that consume it (e.g. LandingHero reads via the real
// hook inside demo-path components). Defaults 'off'; tests override per-case.
const mockVariantBucket = vi.fn<(flag: string) => 'on' | 'off'>(() => 'off');
vi.mock('../../hooks/useVariantBucket', () => ({
  useVariantBucket: (flag: string) => mockVariantBucket(flag),
  BUCKET_STORAGE_KEY: 'classbridge_ab_bucket',
  getOrCreateBucketId: () => 'test-bucket-id',
  hashBucketId: () => 0,
  resolveVariant: () => 'on' as const,
}));

// ─── Imports under test (after mocks) ──────────────────────────────────
import { LandingPageV2 } from '../LandingPageV2';
import { LaunchLandingPage } from '../LaunchLandingPage';
import { buildSectionRegistry } from '../../components/landing/sectionRegistry';

/** All 11 section IDs expected from the CB-LAND-001 registry. */
const EXPECTED_SECTION_IDS = [
  'hero',
  'pain',
  'feature-rows',
  'how',
  'compare',
  'progress',
  'segments',
  'devices',
  'pricing',
  'final-cta',
  'footer',
] as const;

/** Matching ascending order values per §6.136 sequencing. */
const EXPECTED_ORDER_VALUES = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 9999];

// Page-level renders import the full section tree (incl. mascot SVGs) which
// is heavy for jsdom — bump the per-test timeout so the CI default of 5s
// doesn't trip during render time.
describe('LandingPageV2 — page-level integration (S17 #3817)', { timeout: 20_000 }, () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockVariantBucket.mockReturnValue('off');
    // Reset matchMedia to default (no reduced-motion) — individual tests
    // override when needed.
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
      })),
    });
  });

  // ─── 1. Flag-on: all 11 sections render ──────────────────────────────
  describe('flag-on render (landing_v2 = on_100)', () => {
    it('renders LandingPageV2 with all 11 sections via the registry', () => {
      mockVariantBucket.mockReturnValue('on');

      const { container } = renderWithProviders(<LandingPageV2 />);

      const root = container.querySelector('main[data-landing="v2"]');
      expect(root).not.toBeNull();

      // Each section wrapper stamps a stable DOM id + data-section-id
      // attribute (see LandingPageV2.tsx). Assert all 11 are present.
      for (const id of EXPECTED_SECTION_IDS) {
        const wrapper = container.querySelector(`[data-section-id="${id}"]`);
        expect(wrapper, `expected section wrapper for "${id}"`).not.toBeNull();
        expect(wrapper?.getAttribute('id')).toBe(id);
      }

      // No extra sections leak in.
      const allSectionWrappers = container.querySelectorAll('[data-section-id]');
      expect(allSectionWrappers.length).toBe(EXPECTED_SECTION_IDS.length);
    });
  });

  // ─── 2. Flag-off: legacy LaunchLandingPage ──────────────────────────
  describe('flag-off render (landing_v2 = off)', () => {
    it('renders LaunchLandingPage with the .launch-page stable marker', () => {
      mockVariantBucket.mockReturnValue('off');

      const { container } = renderWithProviders(<LaunchLandingPage />);

      // Stable marker #1: the wrapping .launch-page class (predates S17).
      const launchRoot = container.querySelector('.launch-page');
      expect(launchRoot).not.toBeNull();

      // Stable marker #2: the legacy H1 copy, consistent across S17 scope.
      expect(
        screen.getByRole('heading', {
          level: 1,
          name: /AI-Powered Education Platform/i,
        }),
      ).toBeInTheDocument();

      // Sanity: landing-v2 root must NOT appear when flag is off.
      expect(container.querySelector('main[data-landing="v2"]')).toBeNull();
    });
  });

  // ─── 3. Demo CTA smoke — modal mounts on click ──────────────────────
  describe('hero demo CTA smoke', () => {
    it('mounts the InstantTrialModal (mocked) when the hero primary CTA is clicked', async () => {
      mockVariantBucket.mockReturnValue('on');
      const user = userEvent.setup();

      const { container } = renderWithProviders(<LandingPageV2 />);

      // Modal not yet rendered.
      expect(
        screen.queryByTestId('instant-trial-modal-mock'),
      ).not.toBeInTheDocument();

      // Multiple sections share the "30-second demo" copy (hero, pain,
      // final-cta). Scope the query to the hero section wrapper so the
      // assertion is unambiguous and only exercises the hero click path.
      const heroWrapper = container.querySelector<HTMLElement>(
        '[data-section-id="hero"]',
      );
      expect(heroWrapper).not.toBeNull();
      const cta = heroWrapper!.querySelector<HTMLButtonElement>(
        'button.landing-hero__cta--primary',
      );
      expect(cta).not.toBeNull();

      await user.click(cta!);

      expect(
        screen.getByTestId('instant-trial-modal-mock'),
      ).toBeInTheDocument();
    });
  });

  // ─── 4. Reduced motion — ComparisonSplit bounce reset ────────────────
  describe('prefers-reduced-motion', () => {
    it('renders ComparisonSplit without the bounce transform when reduce is true', () => {
      // Override matchMedia BEFORE render so any hook that queries it sees
      // the reduce-true branch. CSS guards hover transform via a
      // @media(prefers-reduced-motion: reduce) rule; we verify the element
      // has no inline transform applied by JS.
      Object.defineProperty(window, 'matchMedia', {
        writable: true,
        value: vi.fn((query: string) => ({
          matches: query.includes('prefers-reduced-motion: reduce'),
          media: query,
          onchange: null,
          addListener: () => {},
          removeListener: () => {},
          addEventListener: () => {},
          removeEventListener: () => {},
          dispatchEvent: () => false,
        })),
      });

      mockVariantBucket.mockReturnValue('on');
      const { container } = renderWithProviders(<LandingPageV2 />);

      const compareWrapper = container.querySelector(
        '[data-section-id="compare"]',
      );
      expect(compareWrapper).not.toBeNull();

      // The bounce effect is a hover transform on `.landing-compare__pill`.
      // Confirm pills render (section mounted correctly) and NO inline
      // transform has been applied (CSS @media-reduce handles the rest).
      const pills = compareWrapper!.querySelectorAll('.landing-compare__pill');
      expect(pills.length).toBeGreaterThan(0);
      for (const pill of Array.from(pills)) {
        const inlineTransform = (pill as HTMLElement).style.transform;
        // Either empty or explicitly reset to 'none' is acceptable.
        expect(inlineTransform === '' || inlineTransform === 'none').toBe(true);
      }
    });
  });

  // ─── 5. Registry order — ascending orders ────────────────────────────
  describe('section registry ordering', () => {
    it('exposes sections in ascending order 10 → 9999', () => {
      const registry = buildSectionRegistry();

      // Length sanity (guards against accidental extra section files).
      expect(registry.length).toBe(EXPECTED_ORDER_VALUES.length);

      const orders = registry.map((s) => s.order);
      expect(orders).toEqual(EXPECTED_ORDER_VALUES);

      // Ascending invariant (redundant but cheap — catches future regressions).
      for (let i = 1; i < orders.length; i++) {
        expect(orders[i]).toBeGreaterThan(orders[i - 1]);
      }

      // IDs match the expected sequence as well.
      expect(registry.map((s) => s.id)).toEqual(Array.from(EXPECTED_SECTION_IDS));
    });
  });

  // ─── 6. Keyboard focus order ─────────────────────────────────────────
  describe('keyboard tab sequence', () => {
    it('places the hero primary CTA as the first focusable element', () => {
      mockVariantBucket.mockReturnValue('on');

      const { container } = renderWithProviders(<LandingPageV2 />);

      // Without a skip-link, the first focusable in DOM order equals the
      // first element tab order would visit. `userEvent.tab()` can exceed
      // the 5s per-test budget on this 11-section DOM under jsdom, so we
      // walk the DOM directly — the assertion is equivalent.
      const focusableSelector = [
        'a[href]',
        'button:not([disabled])',
        'input:not([disabled])',
        'select:not([disabled])',
        'textarea:not([disabled])',
        '[tabindex]:not([tabindex="-1"])',
      ].join(',');
      const first = container.querySelector<HTMLElement>(focusableSelector);
      expect(first).not.toBeNull();

      // The hero primary CTA has a unique class across the page (other
      // sections that share the "30 second demo" label use different
      // class names).
      const heroWrapper = container.querySelector<HTMLElement>(
        '[data-section-id="hero"]',
      );
      const heroCta = heroWrapper!.querySelector<HTMLButtonElement>(
        'button.landing-hero__cta--primary',
      );
      expect(heroCta).not.toBeNull();
      expect(first).toBe(heroCta);
    });

    it('ends keyboard traversal on a footer social link', () => {
      mockVariantBucket.mockReturnValue('on');

      const { container } = renderWithProviders(<LandingPageV2 />);

      // Gather all focusable elements in DOM order. Anything interactive in
      // the footer is what we expect last.
      const focusableSelector = [
        'a[href]',
        'button:not([disabled])',
        'input:not([disabled])',
        'select:not([disabled])',
        'textarea:not([disabled])',
        '[tabindex]:not([tabindex="-1"])',
      ].join(',');
      const focusables = Array.from(
        container.querySelectorAll<HTMLElement>(focusableSelector),
      );
      expect(focusables.length).toBeGreaterThan(0);

      // Last focusable must sit inside the footer section wrapper.
      const last = focusables[focusables.length - 1];
      const footerWrapper = container.querySelector(
        '[data-section-id="footer"]',
      );
      expect(footerWrapper).not.toBeNull();
      expect(footerWrapper!.contains(last)).toBe(true);

      // Assert the computed last focusable is a genuine interactive element
      // (anchor to email/social link, or button). Exhaustively simulating
      // tab-through the full DOM is flaky under jsdom.
      expect(last.tagName === 'A' || last.tagName === 'BUTTON').toBe(true);
    });

    it('contains no elements with a positive tabIndex (no tabIndex > 0)', () => {
      mockVariantBucket.mockReturnValue('on');
      const { container } = renderWithProviders(<LandingPageV2 />);

      const allWithTabIndex = container.querySelectorAll<HTMLElement>(
        '[tabindex]',
      );
      for (const el of Array.from(allWithTabIndex)) {
        const raw = el.getAttribute('tabindex');
        if (raw === null) continue;
        const n = Number(raw);
        // -1 (programmatic focus) and 0 (natural order) are fine. >0 breaks
        // natural tab order and is forbidden by WCAG / §6.136 keyboard spec.
        expect(Number.isNaN(n) || n <= 0).toBe(true);
      }
    });
  });
});
