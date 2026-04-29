/** CB-CMCP-001 M1-B 1B-4 (#4492) — GenericBadge unit tests.
 *
 * Coverage per A1 acceptance:
 * - Badge renders when ``envelope.fallback_used === true``.
 * - Badge is absent when ``envelope.fallback_used === false``.
 * - Color is NOT the only indicator (WCAG 1.4.1): an icon AND a text label
 *   are both present, the icon is ``aria-hidden``, and the visible label
 *   reads "generic — no class-vocab anchoring".
 * - The badge carries an ``aria-label`` so the warning is queryable by
 *   accessible name (we deliberately do NOT use a live-region role —
 *   see component header for rationale).
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import {
  GenericBadge,
  GENERIC_BADGE_LABEL,
  GENERIC_BADGE_ARIA_LABEL,
} from '../GenericBadge';

describe('GenericBadge', () => {
  it('renders the badge when fallbackUsed=true', () => {
    render(<GenericBadge fallbackUsed />);
    const badge = screen.getByTestId('cmcp-generic-badge');
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent(GENERIC_BADGE_LABEL);
  });

  it('renders nothing when fallbackUsed=false', () => {
    const { container } = render(<GenericBadge fallbackUsed={false} />);
    // Nothing visible — neither the badge node nor the label text.
    expect(screen.queryByTestId('cmcp-generic-badge')).not.toBeInTheDocument();
    expect(screen.queryByText(GENERIC_BADGE_LABEL)).not.toBeInTheDocument();
    // The component should also produce no DOM at all (clean unmount path).
    expect(container).toBeEmptyDOMElement();
  });

  it('exposes an aria-label so assistive tech can name the warning', () => {
    render(<GenericBadge fallbackUsed />);
    // The badge is queryable by accessible name (aria-label) without using
    // a live-region role. Live regions don't announce on initial insertion
    // in NVDA+Firefox, and re-announce on re-mount in others — neither is
    // the right behavior for a static label, so we use aria-label instead.
    const byLabel = screen.getByLabelText(GENERIC_BADGE_ARIA_LABEL);
    expect(byLabel).toBeInTheDocument();
    expect(byLabel).toHaveAttribute('aria-label', GENERIC_BADGE_ARIA_LABEL);
  });

  it('uses both an icon AND a text label (color is not the only indicator)', () => {
    const { container } = render(<GenericBadge fallbackUsed />);
    // Icon: present, decorative (aria-hidden), and inside the badge.
    // Query by aria-hidden attribute rather than CSS class so the assertion
    // remains valid if the component is later refactored to use CSS modules.
    const icon = container.querySelector('svg[aria-hidden="true"]');
    expect(icon).not.toBeNull();
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
