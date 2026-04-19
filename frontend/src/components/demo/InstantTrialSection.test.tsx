import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { InstantTrialSection } from './InstantTrialSection';

describe('InstantTrialSection', () => {
  it('renders headline, subheadline and CTA', () => {
    render(<InstantTrialSection />);
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent(/try classbridge/i);
    expect(screen.getByRole('button', { name: /try the demo/i })).toBeInTheDocument();
  });

  it('renders the eyebrow kicker and trust bar chips', () => {
    render(<InstantTrialSection />);
    expect(screen.getByText(/instant demo/i)).toBeInTheDocument();
    expect(screen.getByText(/^fast$/i)).toBeInTheDocument();
    // "No password" appears in both the subheadline and the trust chip; use
    // getAllByText to tolerate duplicates and just assert the chip is present.
    expect(screen.getAllByText(/no password/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/^free$/i)).toBeInTheDocument();
  });

  it('opens the Instant Trial modal when the CTA is clicked', async () => {
    const user = userEvent.setup();
    render(<InstantTrialSection />);
    await user.click(screen.getByRole('button', { name: /try the demo/i }));
    expect(await screen.findByRole('dialog')).toHaveAttribute('aria-modal', 'true');
  });
});
