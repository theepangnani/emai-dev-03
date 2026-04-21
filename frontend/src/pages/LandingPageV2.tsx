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
 */
import { useMemo, type ComponentType } from 'react';
import {
  buildSectionRegistry,
  type LandingSection,
} from '../components/landing/sectionRegistry';
import { useScrollReveal } from '../components/landing/motion';
import '../components/landing/motion.css';

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
 * The wrapper carries `data-landing="v2"` so the motion tokens + `.landing-reveal`
 * rules resolve even though the section components also stamp their own
 * `data-landing` on their root element. Using a wrapper keeps S13 additive —
 * no per-section edits required (idempotent if a section later adds its own
 * reveal hook internally).
 */
function RevealedSection({
  id,
  component: Component,
}: {
  id: string;
  component: ComponentType;
}) {
  const { ref, hidden } = useScrollReveal<HTMLDivElement>();
  return (
    <div
      ref={ref}
      id={id}
      data-section-id={id}
      data-landing="v2"
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
  const registry = useMemo<LandingSection[]>(
    () => sections ?? buildSectionRegistry(),
    [sections],
  );

  return (
    <main data-landing="v2" className="landing-v2-root">
      {registry.length === 0 ? (
        <EmptyRegistryNotice />
      ) : (
        registry.map(({ id, component }) => (
          // Each section wrapper stamps the stable DOM id so anchor links
          // (`/#hero`, `/#pricing`, …) work. Section components render
          // their own <section> landmark underneath. S13 adds scroll-reveal
          // via the wrapper — see `RevealedSection` above.
          <RevealedSection key={id} id={id} component={component} />
        ))
      )}
    </main>
  );
}

export default LandingPageV2;
