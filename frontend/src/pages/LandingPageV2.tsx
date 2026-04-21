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
 */
import { useMemo } from 'react';
import {
  buildSectionRegistry,
  type LandingSection,
} from '../components/landing/sectionRegistry';
import './LandingPageV2.css';

interface LandingPageV2Props {
  /**
   * Optional override of the registry — used by tests to mount the page
   * with an empty or fake section list. Production callers should omit
   * this so the default `import.meta.glob` picks up `./sections/*.tsx`.
   */
  sections?: LandingSection[];
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
        {registry.length === 0 ? (
          <EmptyRegistryNotice />
        ) : (
          mainSections.map(({ id, component: Component }) => (
            // Each section wrapper stamps the stable DOM id so anchor links
            // (`/#hero`, `/#pricing`, …) work. Section components render
            // their own <section> landmark underneath.
            <div key={id} id={id} data-section-id={id}>
              <Component />
            </div>
          ))
        )}
      </main>
      {footerSection ? (
        <div
          key={footerSection.id}
          id={footerSection.id}
          data-section-id={footerSection.id}
        >
          <footerSection.component />
        </div>
      ) : null}
    </>
  );
}

export default LandingPageV2;
