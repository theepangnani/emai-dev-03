/** CB-CMCP-001 M1-B 1B-4 (#4492) — GenericBadge unit tests.
 *
 * Coverage per A1 acceptance:
 * - Badge renders when ``envelope.fallback_used === true``.
 * - Badge is absent when ``envelope.fallback_used === false``.
 * - Color is NOT the only indicator (WCAG 1.4.1): an icon AND a text label
 *   are both present, the icon is ``aria-hidden``, and the visible label
 *   reads "generic — no class-vocab anchoring".
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { GenericBadge, GENERIC_BADGE_LABEL } from '../GenericBadge';

describe('GenericBadge', () => {
  it('renders the badge when fallbackUsed=true', () => {
    render(<GenericBadge fallbackUsed />);
    const badge = screen.getByTestId('cmcp-generic-badge');
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent(GENERIC_BADGE_LABEL);
  });

  it('renders nothing when fallbackUsed=false', () => {
    const { container } = render(<GenericBadge fallbackUsed={false} />);
    // Nothing visible — neither the role=status node nor the label text.
    expect(screen.queryByTestId('cmcp-generic-badge')).not.toBeInTheDocument();
    expect(screen.queryByText(GENERIC_BADGE_LABEL)).not.toBeInTheDocument();
    // The component should also produce no DOM at all (clean unmount path).
    expect(container).toBeEmptyDOMElement();
  });

  it('exposes role="status" so assistive tech announces the warning', () => {
    render(<GenericBadge fallbackUsed />);
    // role=status is the right live-region role for a non-blocking warning.
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('uses both an icon AND a text label (color is not the only indicator)', () => {
    const { container } = render(<GenericBadge fallbackUsed />);
    // Icon: present, decorative (aria-hidden), and inside the badge.
    const icon = container.querySelector('.cmcp-generic-badge-icon');
    expect(icon).not.toBeNull();
    expect(icon?.getAttribute('aria-hidden')).toBe('true');
    // Label: visible text node carries the meaning.
    const label = container.querySelector('.cmcp-generic-badge-label');
    expect(label).not.toBeNull();
    expect(label?.textContent).toBe(GENERIC_BADGE_LABEL);
  });

  it('forwards an optional className for layout overrides', () => {
    render(<GenericBadge fallbackUsed className="my-extra-class" />);
    const badge = screen.getByTestId('cmcp-generic-badge');
    expect(badge.className).toContain('cmcp-generic-badge');
    expect(badge.className).toContain('my-extra-class');
  });
});
