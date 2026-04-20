import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { GatedActionBar, type GatedActionId } from './GatedActionBar';

describe('GatedActionBar', () => {
  it('renders only the actions passed in the actions prop', () => {
    render(<GatedActionBar actions={['download', 'save']} />);
    expect(screen.getByRole('button', { name: /download pdf/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /save to library/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /ask a follow-up/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /more flashcards/i })).toBeNull();
  });

  it('does not render the upsell region on initial mount', () => {
    render(<GatedActionBar actions={['download', 'save']} />);
    expect(
      screen.queryByRole('region', { name: /unlock this feature/i }),
    ).toBeNull();
  });

  it('toggles the upsell card closed when the same button is clicked twice and does not re-fire onUpsell', async () => {
    const user = userEvent.setup();
    const onUpsell = vi.fn<(id: GatedActionId) => void>();
    render(<GatedActionBar actions={['download']} onUpsell={onUpsell} />);
    const download = screen.getByRole('button', { name: /download pdf/i });
    await user.click(download);
    expect(
      screen.getByRole('region', { name: /unlock this feature/i }),
    ).toBeInTheDocument();
    expect(onUpsell).toHaveBeenCalledTimes(1);
    await user.click(download);
    expect(
      screen.queryByRole('region', { name: /unlock this feature/i }),
    ).toBeNull();
    expect(onUpsell).toHaveBeenCalledTimes(1);
    expect(download).toHaveAttribute('aria-expanded', 'false');
  });

  it('dismisses the upsell card when Escape is pressed', async () => {
    const user = userEvent.setup();
    render(<GatedActionBar actions={['download']} />);
    await user.click(screen.getByRole('button', { name: /download pdf/i }));
    expect(
      screen.getByRole('region', { name: /unlock this feature/i }),
    ).toBeInTheDocument();
    await user.keyboard('{Escape}');
    expect(
      screen.queryByRole('region', { name: /unlock this feature/i }),
    ).toBeNull();
  });

  it('opens upsell card with the download headline when download is clicked', async () => {
    const user = userEvent.setup();
    render(<GatedActionBar actions={['download', 'save']} />);
    await user.click(screen.getByRole('button', { name: /download pdf/i }));
    expect(screen.getByText('Want to save these as PDF?')).toBeInTheDocument();
  });

  it('replaces the card headline when a different action is clicked', async () => {
    const user = userEvent.setup();
    render(<GatedActionBar actions={['download', 'save']} />);
    await user.click(screen.getByRole('button', { name: /download pdf/i }));
    expect(screen.getByText('Want to save these as PDF?')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /save to library/i }));
    expect(screen.getByText('Want to save this to your library?')).toBeInTheDocument();
    expect(screen.queryByText('Want to save these as PDF?')).toBeNull();
  });

  it('flips aria-expanded only on the active button', async () => {
    const user = userEvent.setup();
    render(<GatedActionBar actions={['download', 'save', 'follow_up']} />);
    const download = screen.getByRole('button', { name: /download pdf/i });
    const save = screen.getByRole('button', { name: /save to library/i });
    const follow = screen.getByRole('button', { name: /ask a follow-up/i });

    expect(download).toHaveAttribute('aria-expanded', 'false');
    await user.click(download);
    expect(download).toHaveAttribute('aria-expanded', 'true');
    expect(save).toHaveAttribute('aria-expanded', 'false');
    expect(follow).toHaveAttribute('aria-expanded', 'false');
  });

  it('collapses the card when the dismiss close button is clicked', async () => {
    const user = userEvent.setup();
    render(<GatedActionBar actions={['download']} />);
    const download = screen.getByRole('button', { name: /download pdf/i });
    await user.click(download);
    expect(download).toHaveAttribute('aria-expanded', 'true');
    await user.click(screen.getByRole('button', { name: /dismiss/i }));
    expect(screen.queryByText('Want to save these as PDF?')).toBeNull();
    expect(download).toHaveAttribute('aria-expanded', 'false');
  });

  it('invokes onUpsell with the correct actionId on each button click', async () => {
    const user = userEvent.setup();
    const onUpsell = vi.fn<(id: GatedActionId) => void>();
    render(
      <GatedActionBar
        actions={['download', 'save', 'follow_up', 'more_flashcards']}
        onUpsell={onUpsell}
      />,
    );
    await user.click(screen.getByRole('button', { name: /download pdf/i }));
    await user.click(screen.getByRole('button', { name: /save to library/i }));
    await user.click(screen.getByRole('button', { name: /ask a follow-up/i }));
    await user.click(screen.getByRole('button', { name: /more flashcards/i }));
    expect(onUpsell).toHaveBeenNthCalledWith(1, 'download');
    expect(onUpsell).toHaveBeenNthCalledWith(2, 'save');
    expect(onUpsell).toHaveBeenNthCalledWith(3, 'follow_up');
    expect(onUpsell).toHaveBeenNthCalledWith(4, 'more_flashcards');
  });

  it('renders the upsell card as a region labelled "Unlock this feature"', async () => {
    const user = userEvent.setup();
    render(<GatedActionBar actions={['download']} />);
    await user.click(screen.getByRole('button', { name: /download pdf/i }));
    const region = screen.getByRole('region', { name: /unlock this feature/i });
    expect(region).toBeInTheDocument();
    expect(region).toHaveAttribute('id', 'demo-gated-upsell');
  });

  it('waitlist CTA points to /waitlist by default and respects an override', async () => {
    const user = userEvent.setup();
    const { rerender } = render(<GatedActionBar actions={['download']} />);
    await user.click(screen.getByRole('button', { name: /download pdf/i }));
    expect(screen.getByRole('link', { name: /join the waitlist/i })).toHaveAttribute(
      'href',
      '/waitlist',
    );

    rerender(<GatedActionBar actions={['download']} waitlistHref="/signup" />);
    expect(screen.getByRole('link', { name: /join the waitlist/i })).toHaveAttribute(
      'href',
      '/signup',
    );
  });
});
