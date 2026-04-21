/**
 * CB-LAND-001 section registry — glob-additive pattern (#3802 / §6.136.3).
 *
 * Every landing section file under `./sections/*.tsx` exports a `section`
 * object describing itself:
 *
 *     // frontend/src/components/landing/sections/LandingHero.tsx
 *     export function LandingHero() { ... }
 *     export const section = {
 *       id: 'hero',
 *       order: 10,
 *       component: LandingHero,
 *     };
 *
 * Vite's `import.meta.glob` picks up every matching file at build time —
 * so parallel S3-S12 PRs can add new section files without editing any
 * central registration list. This eliminates the merge-conflict hotspot a
 * hand-maintained array would create.
 *
 * ### Per-section contract
 * - `id`        (string) — unique, kebab-case. Rendered as the section's
 *                          DOM id so anchor links / scroll-to work.
 * - `order`     (number) — sort key, ascending. Leave gaps (10, 20, 30…)
 *                          so inserts don't force renumbering.
 * - `component` (React.ComponentType) — the actual section component.
 *                          SHOULD render its own `<section>` landmark.
 *
 * ### How the registry works
 * - `import.meta.glob('./sections/*.tsx', { eager: true })` reads the tiny
 *   `section` metadata (id + order) synchronously so we can sort before
 *   render — no two-pass lazy dance that would flicker on first paint.
 * - Files without a `section` export (helpers like `FeatureRow.tsx`, or
 *   `.test.tsx` files that happen to match the glob) are skipped silently.
 * - Duplicate ids log a warning in dev; the first one wins.
 *
 * If bundle size becomes a concern later, swap the eager glob for a lazy
 * one and render each component inside `<Suspense>` — the public contract
 * (`{ id, order, component }`) stays identical.
 */
import type { ComponentType } from 'react';

export interface LandingSection {
  /** Stable kebab-case id, rendered as the section's DOM id. */
  id: string;
  /** Sort key — lower renders earlier. Leave gaps (10, 20, 30…). */
  order: number;
  /** The section body. */
  component: ComponentType;
}

/** Shape of a section module file — `section` is optional so helper files
 *  under `./sections/` that match the glob (e.g. `FeatureRow.tsx`) don't
 *  break type-checking. They're filtered out at build time. */
interface SectionModule {
  section?: LandingSection;
}

type SectionGlob = Record<string, SectionModule>;

/**
 * Default section glob — `eager: true` so `section` metadata is available
 * synchronously for sorting. Matches `.tsx` files in `./sections/` and
 * EXCLUDES `*.test.tsx` via a negated pattern. Excluding test files at
 * the glob level is critical: if Vite eagerly imports a `*.test.tsx` file
 * outside a test run, the test's `describe()` calls still register into
 * the global vitest runner during `vitest run` and produce phantom tests.
 *
 * The registry also skips entries that don't export a valid `section`
 * object, so helper files under `./sections/` (e.g. `FeatureRow.tsx`) are
 * harmlessly imported-then-ignored.
 */
const defaultSectionGlob = import.meta.glob<SectionModule>(
  ['./sections/*.tsx', '!./sections/*.test.tsx'],
  { eager: true },
);

/**
 * Build the ordered list of landing sections.
 *
 * Exposed as a pure function (rather than a module-level constant) so
 * tests can inject an empty or fake glob.
 */
export function buildSectionRegistry(
  glob: SectionGlob = defaultSectionGlob,
): LandingSection[] {
  const sections: LandingSection[] = [];
  const seenIds = new Set<string>();

  for (const [path, mod] of Object.entries(glob)) {
    // Test files match *.tsx too — they're not sections.
    if (path.includes('.test.')) continue;

    const section = mod?.section;
    if (
      !section ||
      typeof section.id !== 'string' ||
      section.id.trim().length === 0 ||
      typeof section.order !== 'number' ||
      !Number.isFinite(section.order) ||
      typeof section.component !== 'function'
    ) {
      // Helpers without a `section` export — or malformed metadata
      // (empty id, NaN order) — skip silently.
      continue;
    }

    if (seenIds.has(section.id)) {
      if (import.meta.env?.DEV) {
        // eslint-disable-next-line no-console
        console.warn(
          `[landing-v2] duplicate section id "${section.id}" in ${path} — keeping the first occurrence.`,
        );
      }
      continue;
    }
    seenIds.add(section.id);
    sections.push(section);
  }

  return sections.sort(
    (a, b) => a.order - b.order || a.id.localeCompare(b.id),
  );
}
