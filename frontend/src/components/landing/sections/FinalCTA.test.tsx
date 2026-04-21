import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { FinalCTA, section } from './FinalCTA';

// The demo modal pulls in network + focus-trap plumbing that is out of scope
// for this stripe — stub it so the CTA-band tests stay fast and isolated.
vi.mock('../../demo/InstantTrialModal', () => ({
  InstantTrialModal: ({ onClose }: { onClose: () => void }) => (
    <div role="dialog" aria-label="Instant Trial">
      <button onClick={onClose}>close-stub</button>
    </div>
  ),
}));

function renderFinalCTA() {
  return render(
    <MemoryRouter>
      <FinalCTA />
    </MemoryRouter>,
  );
}

describe('FinalCTA', () => {
  it('renders the headline with the italic serif accent fragment', () => {
    renderFinalCTA();
    const heading = screen.getByRole('heading', { level: 2 });
    expect(heading).toHaveTextContent(
      /Give your family the ClassBridge advantage\./i,
    );
    // The accent span is an <em> — assert it wraps the serif fragment.
    const em = heading.querySelector('em');
    expect(em).not.toBeNull();
    expect(em).toHaveTextContent(/ClassBridge advantage\./i);
  });

  it('renders both CTAs — demo primary and waitlist ghost', () => {
    renderFinalCTA();
    expect(
      screen.getByRole('button', { name: /try the 30-second demo/i }),
    ).toBeInTheDocument();
    const waitlistLink = screen.getByRole('link', {
      name: /join the waitlist/i,
    });
    expect(waitlistLink).toHaveAttribute('href', '/waitlist');
  });

  it('opens the InstantTrialModal when the demo CTA is clicked', async () => {
    const user = userEvent.setup();
    renderFinalCTA();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    await user.click(
      screen.getByRole('button', { name: /try the 30-second demo/i }),
    );
    expect(screen.getByRole('dialog', { name: /instant trial/i })).toBeInTheDocument();
  });

  it('exports section metadata for the LandingPageV2 registry', () => {
    expect(section.id).toBe('final-cta');
    expect(section.order).toBe(100);
    expect(section.component).toBe(FinalCTA);
  });
});
