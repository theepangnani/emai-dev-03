import { DemoMascot } from './DemoMascot';
import {
  IconArrowRight,
  IconCheck,
  IconClock,
  IconShield,
  IconSparkles,
} from './icons';
import './InstantTrialModal.css';

interface InstantTrialSectionProps {
  /** Callback fired when the CTA is clicked; parent owns modal state. */
  onOpen: () => void;
  /** Optional override for the section headline. */
  headline?: string;
  /** Optional override for the sub-headline. */
  subheadline?: string;
  /** Optional override for the CTA label. */
  ctaLabel?: string;
}

/**
 * Landing-page section that advertises the instant demo and notifies the
 * parent to open the Instant Trial modal when the CTA is clicked.
 *
 * FE5 is responsible for mounting this behind the feature flag — this
 * component is purely presentational.
 */
export function InstantTrialSection({
  onOpen,
  headline = 'Try ClassBridge in 30 seconds',
  subheadline = 'No password, no download. Pick a sample, watch it stream, and see how ClassBridge turns class work into clear next steps.',
  ctaLabel = 'Try the demo',
}: InstantTrialSectionProps) {
  return (
    <section
      id="instant-trial"
      className="instant-trial-section"
      aria-labelledby="instant-trial-heading"
    >
      <div className="instant-trial-inner">
        <div className="instant-trial-content">
          <p className="demo-eyebrow">Instant Demo &middot; 30 Seconds</p>
          <h2 id="instant-trial-heading">{headline}</h2>
          <p>{subheadline}</p>
          <button
            type="button"
            className="instant-trial-cta"
            onClick={onOpen}
          >
            <IconSparkles size={18} aria-hidden />
            <span>{ctaLabel}</span>
            <IconArrowRight size={18} aria-hidden />
          </button>
          <div className="demo-trust-bar" aria-label="Demo highlights">
            <span className="demo-trust-chip">
              <IconClock size={14} aria-hidden />
              <span>Fast</span>
            </span>
            <span className="demo-trust-chip">
              <IconShield size={14} aria-hidden />
              <span>No password</span>
            </span>
            <span className="demo-trust-chip">
              <IconCheck size={14} aria-hidden />
              <span>Free</span>
            </span>
          </div>
        </div>
        <div className="instant-trial-mascot" aria-hidden="true">
          <DemoMascot size={72} mood="greeting" />
        </div>
      </div>
    </section>
  );
}

export default InstantTrialSection;
