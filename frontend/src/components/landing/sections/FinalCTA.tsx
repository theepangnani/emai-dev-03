import { useState } from 'react';
import { Link } from 'react-router-dom';
import { InstantTrialModal } from '../../demo/InstantTrialModal';
import './FinalCTA.css';

/**
 * CB-LAND-001 S12A — Final CTA band.
 *
 * Full-width cyan-gradient closer with a serif-italic headline accent and
 * two stacked-on-mobile CTAs: the 30-second demo (opens InstantTrialModal)
 * and the waitlist (routes to /waitlist).
 *
 * Rendered by the S2 LandingPageV2 scaffold via the exported `section`
 * registry entry (order: 100 — second-to-last, before the footer).
 */
export function FinalCTA() {
  const [demoOpen, setDemoOpen] = useState(false);

  return (
    <>
      <section
        data-landing="v2"
        className="landing-final-cta"
        aria-labelledby="landing-final-cta-heading"
      >
        <div className="landing-final-cta__inner">
          <h2
            id="landing-final-cta-heading"
            className="landing-final-cta__headline"
          >
            Give your family the{' '}
            <em className="landing-final-cta__accent">
              ClassBridge advantage.
            </em>
          </h2>
          <div className="landing-final-cta__actions">
            <button
              type="button"
              className="landing-final-cta__btn landing-final-cta__btn--primary"
              onClick={() => setDemoOpen(true)}
            >
              Try the 30-second demo
            </button>
            <Link
              to="/waitlist"
              className="landing-final-cta__btn landing-final-cta__btn--ghost"
            >
              Join the Waitlist
            </Link>
          </div>
        </div>
      </section>
      {demoOpen && (
        <InstantTrialModal onClose={() => setDemoOpen(false)} />
      )}
    </>
  );
}

export const section = {
  id: 'final-cta',
  order: 100,
  component: FinalCTA,
};

export default FinalCTA;
