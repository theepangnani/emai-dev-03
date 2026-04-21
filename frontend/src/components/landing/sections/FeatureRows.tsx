/**
 * CB-LAND-001 S5 — FeatureRows (section container)
 *
 * Renders the §4 "Every signal" section of the landing v2 redesign as 6
 * alternating pastel rows driven by `content/features.ts`. Kicker + headline
 * from §3 are folded in as the section header (per requirements §6.136.1 §3-4).
 *
 * Row ordering and variants are authored in `features.ts`; this container is
 * presentation-only. Every odd-indexed row flips to text-right / mockup-left.
 *
 * Exported via the glob-registry as `section = { id, order, component }` so
 * the top-level LandingPageV2 can slot it into the long-scroll page.
 */

import './FeatureRows.css';
import { FeatureRow } from './FeatureRow';
import { features } from '../content/features';

export function FeatureRows() {
  return (
    <section
      data-landing="v2"
      className="landing-feature-rows"
      aria-labelledby="feature-rows-heading"
    >
      <header className="landing-feature-rows__header">
        <p className="landing-feature-rows__kicker">Introducing ClassBridge&hellip;</p>
        <h2
          id="feature-rows-heading"
          className="landing-feature-rows__headline"
        >
          One platform. Every role. <em>Every signal.</em>
        </h2>
      </header>
      <div className="landing-feature-rows__list">
        {features.map((feature, index) => (
          <FeatureRow
            key={feature.id}
            content={feature}
            reversed={index % 2 === 1}
          />
        ))}
      </div>
    </section>
  );
}

export const section = {
  id: 'feature-rows',
  order: 30,
  component: FeatureRows,
};

export default FeatureRows;
