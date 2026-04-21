import { useState } from 'react';
import { Link } from 'react-router-dom';
import { InstantTrialModal } from '../../demo/InstantTrialModal';
import './LandingHero.css';

/**
 * LandingHero — CB-LAND-001 S3 (#3803).
 *
 * Mindgrasp-inspired hero: serif-italic accent on a sans-serif headline,
 * two stacked CTAs on the left, a placeholder product mockup on the right,
 * and a "TRUSTED BY" strip of Ontario school-board chips below the hero.
 *
 * Root carries `data-landing="v2"` so the S1 token set (§6.136.1 §1) resolves.
 * Primary CTA opens the existing `InstantTrialModal`; secondary CTA is a
 * router `<Link>` to `/waitlist`.
 *
 * NOTE: Board names are hardcoded here — sourcing from TuesdayMirror requires
 * touching `components/demo/**` which is out of scope for CB-LAND-001. Tracked
 * via CB-LAND-001-fast-follow "S3-followup: source trust-bar from TuesdayMirror data".
 */

const TRUST_BAR_BOARDS = ['YRDSB', 'TDSB', 'DDSB', 'PDSB', 'OCDSB'] as const;

export function LandingHero() {
  const [demoOpen, setDemoOpen] = useState<boolean>(false);

  return (
    <section data-landing="v2" className="landing-hero" aria-labelledby="landing-hero-title">
      <div className="landing-hero__inner">
        <div className="landing-hero__content">
          <h1 id="landing-hero-title" className="landing-hero__headline">
            Close the homework gap. Together, in <em>one place.</em>
          </h1>
          <p className="landing-hero__subhead">
            One calm platform for parents, students, and teachers — so nobody
            falls behind on what matters this week.
          </p>
          <div className="landing-hero__ctas">
            <button
              type="button"
              className="landing-hero__cta landing-hero__cta--primary"
              onClick={() => setDemoOpen(true)}
            >
              Try the 30-second demo
            </button>
            <Link
              to="/waitlist"
              className="landing-hero__cta landing-hero__cta--ghost"
            >
              Join the waitlist
            </Link>
          </div>
        </div>
        <div className="landing-hero__mockup" role="presentation" aria-hidden="true">
          <div className="landing-hero__mockup-bar" />
          <div className="landing-hero__mockup-panel landing-hero__mockup-panel--wide" />
          <div className="landing-hero__mockup-panel landing-hero__mockup-panel--narrow" />
        </div>
      </div>
      <div className="landing-hero__trust">
        <p className="landing-hero__trust-kicker">TRUSTED BY ONTARIO SCHOOL BOARDS</p>
        <ul className="landing-hero__trust-list" aria-label="Ontario school boards">
          {TRUST_BAR_BOARDS.map((board) => (
            <li key={board} className="landing-hero__trust-chip">
              {board}
            </li>
          ))}
        </ul>
      </div>
      {demoOpen && <InstantTrialModal onClose={() => setDemoOpen(false)} />}
    </section>
  );
}

/**
 * Section-registry entry. S2 (scaffold) consumes `{ id, order, component }`
 * to render sections in-order. Exporting here is harmless if S2 hasn't merged.
 */
export const section = { id: 'hero', order: 10, component: LandingHero };
