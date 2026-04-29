/** CB-EDIGEST-002 E5 (#4593) — EmptyStates unit tests. */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { EmptyStates } from './EmptyStates';

describe('EmptyStates', () => {
  it('calm: renders correct copy + Refresh CTA when onRefresh provided', async () => {
    const onRefresh = vi.fn();
    const user = userEvent.setup();
    render(<EmptyStates kind="calm" onRefresh={onRefresh} />);
    expect(screen.getByText(/Nothing urgent today/)).toBeInTheDocument();
    const btn = screen.getByRole('button', { name: /^Refresh$/ });
    await user.click(btn);
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  it('calm: omits Refresh button when onRefresh is not provided', () => {
    render(<EmptyStates kind="calm" />);
    expect(screen.getByText(/Nothing urgent today/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Refresh$/ })).not.toBeInTheDocument();
  });

  it('no_kids: renders + onAddKids CTA fires', async () => {
    const onAddKids = vi.fn();
    const user = userEvent.setup();
    render(<EmptyStates kind="no_kids" onAddKids={onAddKids} />);
    expect(screen.getByText(/Add your kids to start/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /^Add a kid$/ }));
    expect(onAddKids).toHaveBeenCalledTimes(1);
  });

  it('paused: renders + onResume CTA fires', async () => {
    const onResume = vi.fn();
    const user = userEvent.setup();
    render(<EmptyStates kind="paused" onResume={onResume} />);
    expect(screen.getByText(/Digests paused/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /^Resume$/ }));
    expect(onResume).toHaveBeenCalledTimes(1);
  });

  it('auth_expired: renders + onReconnectGmail CTA fires', async () => {
    const onReconnectGmail = vi.fn();
    const user = userEvent.setup();
    render(<EmptyStates kind="auth_expired" onReconnectGmail={onReconnectGmail} />);
    expect(screen.getByText(/Reconnect Gmail/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /^Reconnect$/ }));
    expect(onReconnectGmail).toHaveBeenCalledTimes(1);
  });

  it('first_run: renders + onRefresh CTA fires', async () => {
    const onRefresh = vi.fn();
    const user = userEvent.setup();
    render(<EmptyStates kind="first_run" onRefresh={onRefresh} />);
    expect(screen.getByText(/Your first digest is on the way/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Refresh now/i }));
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  it('legacy_blob: renders sanitized HTML', async () => {
    const blob = '<p>Hello <strong>parent</strong></p>';
    render(<EmptyStates kind="legacy_blob" legacyBlob={blob} />);
    const container = await screen.findByTestId('legacy-blob-html');
    // strong tag preserved through sanitizer
    expect(container.querySelector('strong')).not.toBeNull();
    expect(container.textContent).toMatch(/Hello parent/);
  });

  it('legacy_blob: <script> tag is NOT in the DOM after sanitization', async () => {
    const malicious =
      '<p>Greeting</p><script data-testid="bad-script">window.__pwned = true;</script>';
    const { container } = render(
      <EmptyStates kind="legacy_blob" legacyBlob={malicious} />,
    );
    const blobHtml = await screen.findByTestId('legacy-blob-html');
    // Wait for sanitized content to settle
    await waitFor(() => {
      expect(blobHtml.textContent).toMatch(/Greeting/);
    });
    // Script element MUST NOT be present anywhere in the rendered tree.
    expect(container.querySelector('script[data-testid="bad-script"]')).toBeNull();
    expect(container.querySelector('script')).toBeNull();
    // Sanity: side effect of the script must not have fired.
    expect((window as unknown as { __pwned?: boolean }).__pwned).toBeUndefined();
  });
});
