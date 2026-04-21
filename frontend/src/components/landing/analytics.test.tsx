/**
 * CB-LAND-001 S16 — Landing v2 analytics funnel smoke test.
 *
 * Confirms the hero → demo CTA step of the funnel:
 *   `landing_v2.cta_click` with { cta:'demo', section:'hero' }
 *
 * Downstream (CB-DEMO-001 `demo.create_session` → `demo.verify_email`) is
 * exercised in the demo stripe's own tests.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithRouter } from '../../test/helpers';
import { LandingHero } from './sections/LandingHero';
import {
  emitCtaClick,
  LANDING_V2_ANALYTICS_SAMPLE_RATE,
} from './analytics';

// The InstantTrialModal pulls in network + focus-trap plumbing that's out
// of scope for a funnel-event test. Stub it so the CTA click stays fast.
vi.mock('../demo/InstantTrialModal', () => ({
  InstantTrialModal: ({ onClose }: { onClose: () => void }) => (
    <div role="dialog" aria-label="Instant Trial">
      <button onClick={onClose}>close-stub</button>
    </div>
  ),
}));

interface DataLayerWindow extends Window {
  dataLayer?: Array<Record<string, unknown>>;
}

function layer(): Array<Record<string, unknown>> {
  return ((window as DataLayerWindow).dataLayer ??= []);
}

describe('landing v2 analytics', () => {
  beforeEach(() => {
    (window as DataLayerWindow).dataLayer = [];
  });

  it('emits landing_v2.cta_click with cta=demo, section=hero when the hero demo CTA is clicked', async () => {
    const user = userEvent.setup();
    renderWithRouter(<LandingHero />);

    await user.click(
      screen.getByRole('button', { name: /try the 30-second demo/i }),
    );

    const clicks = layer().filter(
      (e) => e.event === 'landing_v2.cta_click',
    );
    expect(clicks).toHaveLength(1);
    expect(clicks[0]).toMatchObject({
      event: 'landing_v2.cta_click',
      cta: 'demo',
      section: 'hero',
    });
  });

  it('exports a 100% default sample rate (first 14 days per §6.136.7)', () => {
    expect(LANDING_V2_ANALYTICS_SAMPLE_RATE).toBe(1.0);
  });

  it('direct emitCtaClick call pushes the same envelope', () => {
    emitCtaClick('waitlist', 'final-cta');
    const evt = layer().at(-1);
    expect(evt).toMatchObject({
      event: 'landing_v2.cta_click',
      cta: 'waitlist',
      section: 'final-cta',
    });
  });
});
