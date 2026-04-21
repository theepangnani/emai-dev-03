/**
 * LandingPageV2 — CB-LAND-001 scaffold (#3802, §6.136.3 / §6.136.8).
 *
 * Minimal shell. The visual content is supplied by sibling PRs S3-S12
 * under `frontend/src/components/landing/sections/*.tsx`. Each section
 * registers itself via an `export const section = { id, order, component }`
 * consumed by `../components/landing/sectionRegistry.ts`.
 *
 * The outer wrapper sets `data-landing="v2"` so the scoped design tokens
 * from S1 (landing-v2 fonts / palette / motion) activate.
 *
 * S14 (#3814) — WCAG 2.1 AA: a skip-to-content link precedes <main>, the
 * main landmark carries id="main" for the link target, and the footer
 * section (if present in the registry) is rendered OUTSIDE <main> so the
 * page has a single top-level <footer> landmark.
 *
 * S15 (#3815, §6.136.6): `<LandingSeo />` injects meta / OG / Twitter /
 * JSON-LD into <head>. Sections still ship in one chunk — see
 * `sectionRegistry.ts` for the fast-follow that moves each section
 * behind a dynamic import.
 */
import { useMemo, type ComponentType } from 'react';
import {
  buildSectionRegistry,
  type LandingSection,
} from '../components/landing/sectionRegistry';
import { useScrollReveal } from '../components/landing/motion';
import '../components/landing/motion.css';
import { LandingSeo } from '../components/landing/LandingSeo';
import { useLandingFonts } from '../components/landing/fonts';
import './LandingPageV2.css';

interface LandingPageV2Props {
  /**
   * Optional override of the registry — used by tests to mount the page
   * with an empty or fake section list. Production callers should omit
   * this so the default `import.meta.glob` picks up `./sections/*.tsx`.
   */
  sections?: LandingSection[];
}

/**
 * Wraps each registered section in a scroll-reveal `<div>` (CB-LAND-001 S13).
 * The outer `<main data-landing="v2">` already scopes the page so the motion
 * tokens + `.landing-reveal` rules resolve via the ancestor — no need to
 * double-stamp `data-landing` on each wrapper. Using a wrapper keeps S13
 * additive: no per-section edits required, idempotent if a section later adds
 * its own reveal hook internally.
 *
 * Deep-link safety (I3): if the URL hash points at this section on mount, we
 * skip the hidden state so the browser's scroll-to-anchor lands on a visible
 * element (IntersectionObserver won't re-fire once the page has already
 * scrolled past the reveal threshold).
 */
function RevealedSection({
  id,
  component: Component,
}: {
  id: string;
  component: ComponentType;
}) {
  const initiallyRevealed =
    typeof window !== 'undefined' && window.location.hash === `#${id}`;
  const { ref, hidden } = useScrollReveal<HTMLDivElement>({ initiallyRevealed });
  return (
    <div
      ref={ref}
      id={id}
      data-section-id={id}
      className={hidden}
    >
      <Component />
    </div>
  );
}

/** Empty-state placeholder (only renders before any S3-S12 PR has shipped). */
function EmptyRegistryNotice() {
  // Intentionally minimal — S3 adds the real hero; this just prevents a
  // blank page if the flag is flipped on with no sections merged yet.
  return (
    <section
      aria-label="Landing page under construction"
      data-testid="landing-v2-empty"
      style={{ padding: '4rem 1.5rem', textAlign: 'center' }}
    >
      <p>Landing v2 scaffold active — no sections registered yet.</p>
    </section>
  );
}

export function LandingPageV2({ sections }: LandingPageV2Props = {}) {
  // Inject landing-v2 Google Fonts on mount, remove on unmount (#3873).
  // Keeps the 80-160 KB stylesheet off every non-landing route.
  useLandingFonts();

  const registry = useMemo<LandingSection[]>(
    () => sections ?? buildSectionRegistry(),
    [sections],
  );

  // Split footer (id === 'footer') out of <main> so the <footer> landmark
  // sits at the page level rather than nested inside main. Any non-footer
  // entries stay in registry order.
  const mainSections = registry.filter((s) => s.id !== 'footer');
  const footerSection = registry.find((s) => s.id === 'footer');

  return (
    <>
      <a href="#main" className="landing-v2-skip-link">
        Skip to main content
      </a>
      <main id="main" data-landing="v2" className="landing-v2-root">
        <LandingSeo />
        {registry.length === 0 ? (
          <EmptyRegistryNotice />
        ) : (
          mainSections.map(({ id, component }) => (
            // Each section wrapper stamps the stable DOM id so anchor links
            // (`/#hero`, `/#pricing`, …) work. Section components render
            // their own <section> landmark underneath. S13 adds scroll-reveal
            // via the wrapper — see `RevealedSection` above.
            <RevealedSection key={id} id={id} component={component} />
          ))
        )}
      </main>
      {footerSection ? (
        <RevealedSection
          key={footerSection.id}
          id={footerSection.id}
          component={footerSection.component}
        />
      ) : null}
    </>
  );
}

export default LandingPageV2;
