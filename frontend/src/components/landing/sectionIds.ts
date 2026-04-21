/**
 * CB-LAND-001 — shared landing-v2 section IDs.
 *
 * Single source of truth for section slot keys used by `sectionRegistry`,
 * `LandingPageV2`'s main/footer split, anchor links, and tests. Prevents
 * typos like `"footers"` from silently breaking the split, since TypeScript
 * narrows every reference to the union type.
 */
export const LANDING_SECTION_ID = {
  nav: 'nav',
  hero: 'hero',
  pain: 'pain',
  featureRows: 'feature-rows',
  how: 'how',
  compare: 'compare',
  progress: 'progress',
  segments: 'segments',
  devices: 'devices',
  pricing: 'pricing',
  finalCta: 'final-cta',
  footer: 'footer',
} as const;
export type LandingSectionId = (typeof LANDING_SECTION_ID)[keyof typeof LANDING_SECTION_ID];
