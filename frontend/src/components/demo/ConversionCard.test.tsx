import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ConversionCard } from './ConversionCard';

describe('ConversionCard', () => {
  it('shows the waitlist position text and three benefit bullets', () => {
    const { container } = render(
      <ConversionCard position={347} totalPreview={1204} onVerify={() => {}} />,
    );
    expect(screen.getByText('#347')).toBeInTheDocument();
    expect(screen.getByText(/of 1,204/)).toBeInTheDocument();
    const items = screen.getAllByRole('listitem');
    expect(items).toHaveLength(3);
    // Each bullet is prefixed with a check icon; total SVGs include header + 3 bullets + CTA icons.
    expect(container.querySelectorAll('li > svg').length).toBe(3);
  });

  it('hides the "of N" phrase when total is missing or smaller than position', () => {
    render(<ConversionCard position={50} onVerify={() => {}} />);
    expect(screen.queryByText(/of /)).toBeNull();
  });

  it('calls onVerify when the primary CTA is clicked', async () => {
    const user = userEvent.setup();
    const onVerify = vi.fn();
    render(<ConversionCard position={1} onVerify={onVerify} />);
    await user.click(screen.getByRole('button', { name: /verify my email/i }));
    expect(onVerify).toHaveBeenCalledOnce();
  });
});
