import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { InstantTrialSection } from './InstantTrialSection';

describe('InstantTrialSection', () => {
  it('renders headline, subheadline and CTA', () => {
    render(<InstantTrialSection />);
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent(/try classbridge/i);
    expect(screen.getByRole('button', { name: /try now/i })).toBeInTheDocument();
  });

  it('opens the Instant Trial modal when the CTA is clicked', async () => {
    const user = userEvent.setup();
    render(<InstantTrialSection />);
    await user.click(screen.getByRole('button', { name: /try now/i }));
    expect(await screen.findByRole('dialog')).toHaveAttribute('aria-modal', 'true');
  });
});
