import { useState } from 'react';
import { InstantTrialModal } from './InstantTrialModal';
import './InstantTrialModal.css';

interface InstantTrialSectionProps {
  /** Optional override for the section headline. */
  headline?: string;
  /** Optional override for the sub-headline. */
  subheadline?: string;
  /** Optional override for the CTA label. */
  ctaLabel?: string;
}

/**
 * Landing-page section that advertises the instant demo and opens the
 * Instant Trial modal when the CTA is clicked.
 *
 * FE5 is responsible for mounting this behind the feature flag — this
 * component is intentionally self-contained and does not touch the page.
 */
export function InstantTrialSection({
  headline = 'Try ClassBridge in 30 seconds',
  subheadline = 'No password, no download. Pick a sample, watch it stream, and see how ClassBridge turns class work into clear next steps.',
  ctaLabel = 'Try Now',
}: InstantTrialSectionProps) {
  const [open, setOpen] = useState(false);

  return (
    <section className="instant-trial-section" aria-labelledby="instant-trial-heading">
      <div className="instant-trial-inner">
        <h2 id="instant-trial-heading">{headline}</h2>
        <p>{subheadline}</p>
        <button
          type="button"
          className="instant-trial-cta"
          onClick={() => setOpen(true)}
        >
          {ctaLabel}
        </button>
      </div>
      {open && <InstantTrialModal onClose={() => setOpen(false)} />}
    </section>
  );
}

export default InstantTrialSection;
