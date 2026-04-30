import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ItemDrilldownModal, type DrilldownItem } from './ItemDrilldownModal';

function makeItem(overrides: Partial<DrilldownItem> = {}): DrilldownItem {
  return {
    id: 'task-1',
    title: 'Read chapter 4 of The Outsiders',
    due_date: '2026-05-02T15:00:00Z',
    course_or_context: 'ENG2D · Ms. Patel',
    source_email_id: 'email-99',
    source_email_subject: 'Reminder: ENG2D reading due Friday',
    source_email_body: '<p>Please read chapter 4 by Friday.</p>',
    source_email_from: 'ms.patel@school.example',
    source_email_received: '2026-04-29T08:00:00Z',
    ...overrides,
  };
}

const baseProps = {
  open: true,
  item: makeItem(),
  onClose: () => {},
  onMarkDone: async () => {},
  onSnooze: async () => {},
};

describe('ItemDrilldownModal', () => {
  it('renders nothing when open=false', () => {
    const { container } = render(
      <ItemDrilldownModal {...baseProps} open={false} />,
    );
    expect(container.innerHTML).toBe('');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('renders title, body, and action row when open', async () => {
    render(<ItemDrilldownModal {...baseProps} />);

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: /read chapter 4/i }),
    ).toBeInTheDocument();

    // Email body uses lazy DOMPurify — wait for it to render.
    await waitFor(() => {
      expect(screen.getByTestId('idm-email-body')).toBeInTheDocument();
    });
    expect(screen.getByTestId('idm-email-body').textContent).toMatch(
      /please read chapter 4/i,
    );

    expect(screen.getByTestId('idm-mark-done')).toBeInTheDocument();
    expect(screen.getByTestId('idm-snooze-1')).toBeInTheDocument();
    expect(screen.getByTestId('idm-snooze-7')).toBeInTheDocument();
    expect(screen.getByTestId('idm-close-action')).toBeInTheDocument();
  });

  it('calls onMarkDone with item.id and shows loading state during await', async () => {
    let resolveAction: (() => void) | null = null;
    const onMarkDone = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveAction = resolve;
        }),
    );
    render(<ItemDrilldownModal {...baseProps} onMarkDone={onMarkDone} />);

    await userEvent.click(screen.getByTestId('idm-mark-done'));
    expect(onMarkDone).toHaveBeenCalledWith('task-1');

    // Loading state — button label flips, all action buttons disabled.
    await waitFor(() => {
      expect(screen.getByTestId('idm-mark-done')).toHaveTextContent(/marking/i);
    });
    expect(screen.getByTestId('idm-mark-done')).toBeDisabled();
    expect(screen.getByTestId('idm-snooze-1')).toBeDisabled();
    expect(screen.getByTestId('idm-snooze-7')).toBeDisabled();
    expect(screen.getByTestId('idm-close-action')).toBeDisabled();

    // Resolve and verify the loading state clears.
    resolveAction!();
    await waitFor(() => {
      expect(screen.getByTestId('idm-mark-done')).toHaveTextContent(/mark done/i);
    });
    expect(screen.getByTestId('idm-mark-done')).not.toBeDisabled();
  });

  it('calls onSnooze with (item.id, 1) when Snooze 1 day is clicked', async () => {
    const onSnooze = vi.fn().mockResolvedValue(undefined);
    render(<ItemDrilldownModal {...baseProps} onSnooze={onSnooze} />);

    await userEvent.click(screen.getByTestId('idm-snooze-1'));
    expect(onSnooze).toHaveBeenCalledWith('task-1', 1);
  });

  it('calls onSnooze with (item.id, 7) when Snooze until next week is clicked', async () => {
    const onSnooze = vi.fn().mockResolvedValue(undefined);
    render(<ItemDrilldownModal {...baseProps} onSnooze={onSnooze} />);

    await userEvent.click(screen.getByTestId('idm-snooze-7'));
    expect(onSnooze).toHaveBeenCalledWith('task-1', 7);
  });

  it('calls onClose when X button or backdrop is clicked', async () => {
    const onClose = vi.fn();
    const { container } = render(
      <ItemDrilldownModal {...baseProps} onClose={onClose} />,
    );

    // X button (header close — has the same aria-label so we scope to the
    // dedicated `idm-close` class to disambiguate from the tertiary Close
    // action below).
    const xBtn = container.querySelector('.idm-close') as HTMLButtonElement;
    expect(xBtn).not.toBeNull();
    await userEvent.click(xBtn);
    expect(onClose).toHaveBeenCalledTimes(1);

    // Tertiary Close action button.
    await userEvent.click(screen.getByTestId('idm-close-action'));
    expect(onClose).toHaveBeenCalledTimes(2);

    // Backdrop click — clicking the overlay (not the inner modal) triggers close.
    const overlay = container.querySelector('.idm-overlay') as HTMLElement;
    expect(overlay).not.toBeNull();
    fireEvent.click(overlay);
    expect(onClose).toHaveBeenCalledTimes(3);
  });

  it('calls onClose when Escape key is pressed', async () => {
    const onClose = vi.fn();
    render(<ItemDrilldownModal {...baseProps} onClose={onClose} />);

    // useFocusTrap binds keydown to the dialog container.
    const dialog = screen.getByRole('dialog');
    fireEvent.keyDown(dialog, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('sanitizes email body — script tags stripped, safe HTML preserved', async () => {
    const item = makeItem({
      source_email_body:
        "<script>window.__xss = true;</script><p>safe</p>",
    });
    const { container } = render(
      <ItemDrilldownModal {...baseProps} item={item} />,
    );

    // Wait for DOMPurify to load + sanitize.
    await waitFor(() => {
      expect(screen.getByTestId('idm-email-body')).toBeInTheDocument();
    });

    const body = screen.getByTestId('idm-email-body');
    // Safe markup preserved.
    expect(body.querySelector('p')?.textContent).toBe('safe');
    // <script> tag removed entirely from the rendered DOM.
    expect(container.querySelector('script')).toBeNull();
    expect(body.innerHTML.toLowerCase()).not.toContain('<script');
    // And the side-effect of the malicious script never ran.
    expect((window as unknown as { __xss?: boolean }).__xss).toBeUndefined();
  });

  it('renders the Phase 2 Arc Q&A slot as hidden', () => {
    render(<ItemDrilldownModal {...baseProps} />);
    const slot = screen.getByTestId('phase2-arc-qa-slot');
    expect(slot).toBeInTheDocument();
    expect(slot).not.toBeVisible();
    expect(slot).toHaveAttribute('hidden');
  });
});
