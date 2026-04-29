/** CB-CMCP-001 M3-B 3B-2 (#4578) — SelfStudyBadge unit tests.
 *
 * Coverage:
 * - Renders icon + visible text label "AI-generated, not teacher-approved".
 * - aria-label set so the warning is queryable by accessible name.
 * - Color is NOT the only indicator (WCAG 1.4.1): icon (aria-hidden) + text
 *   label are both present.
 * - Size variants render their corresponding modifier class.
 * - Optional tooltip is exposed via title= and folded into the accessible
 *   name.
 * - Custom className composes onto the badge root.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import {
  SelfStudyBadge,
  SELF_STUDY_BADGE_LABEL,
  SELF_STUDY_BADGE_ARIA_LABEL,
} from '../SelfStudyBadge';

describe('SelfStudyBadge', () => {
  it('uses the exact spec literal "AI-generated, not teacher-approved"', () => {
    // Pin the label literal: GH #4578 acceptance requires this exact copy.
    // Other tests assert against the SELF_STUDY_BADGE_LABEL constant — if a
    // future refactor accidentally renames the constant value, those tests
    // would stay green but the on-screen warning copy would silently drift.
    // This single-line guard closes that mutation-coverage gap.
    expect(SELF_STUDY_BADGE_LABEL).toBe('AI-generated, not teacher-approved');
  });

  it('renders the icon and the visible text label', () => {
    const { container } = render(<SelfStudyBadge />);
    const badge = screen.getByTestId('cmcp-self-study-badge');
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent(SELF_STUDY_BADGE_LABEL);

    // Icon is present and decorative (aria-hidden).
    const icon = container.querySelector('svg[aria-hidden="true"]');
    expect(icon).not.toBeNull();
  });

  it('exposes an aria-label so assistive tech can name the warning', () => {
    render(<SelfStudyBadge />);
    const byLabel = screen.getByLabelText(SELF_STUDY_BADGE_ARIA_LABEL);
    expect(byLabel).toBeInTheDocument();
    expect(byLabel).toHaveAttribute('aria-label', SELF_STUDY_BADGE_ARIA_LABEL);
  });

  it('uses both an icon AND a text label (color is not the only indicator)', () => {
    const { container } = render(<SelfStudyBadge />);
    // Icon: present, decorative (aria-hidden).
    const icon = container.querySelector('svg[aria-hidden="true"]');
    expect(icon).not.toBeNull();
    // Label: visible text node carries the meaning.
    const label = container.querySelector('.cmcp-self-study-badge-label');
    expect(label).not.toBeNull();
    expect(label?.textContent).toBe(SELF_STUDY_BADGE_LABEL);
  });

  it('defaults to the small size variant', () => {
    render(<SelfStudyBadge />);
    const badge = screen.getByTestId('cmcp-self-study-badge');
    expect(badge.className).toContain('cmcp-self-study-badge--sm');
    expect(badge.className).not.toContain('cmcp-self-study-badge--md');
  });

  it('renders the medium size variant when size="md"', () => {
    render(<SelfStudyBadge size="md" />);
    const badge = screen.getByTestId('cmcp-self-study-badge');
    expect(badge.className).toContain('cmcp-self-study-badge--md');
    expect(badge.className).not.toContain('cmcp-self-study-badge--sm');
  });

  it('exposes the optional tooltip via title= and folds it into the accessible name', () => {
    const tooltipCopy =
      'This artifact was generated without a teacher review.';
    render(<SelfStudyBadge tooltip={tooltipCopy} />);
    const badge = screen.getByTestId('cmcp-self-study-badge');
    expect(badge).toHaveAttribute('title', tooltipCopy);
    // aria-label includes both the canonical warning and the tooltip detail.
    const ariaLabel = badge.getAttribute('aria-label') || '';
    expect(ariaLabel).toContain(SELF_STUDY_BADGE_ARIA_LABEL);
    expect(ariaLabel).toContain(tooltipCopy);
  });

  it('omits the title attribute when no tooltip is provided', () => {
    render(<SelfStudyBadge />);
    const badge = screen.getByTestId('cmcp-self-study-badge');
    expect(badge).not.toHaveAttribute('title');
  });

  it('forwards an optional className for layout overrides', () => {
    render(<SelfStudyBadge className="my-extra-class" />);
    const badge = screen.getByTestId('cmcp-self-study-badge');
    expect(badge.className).toContain('cmcp-self-study-badge');
    expect(badge.className).toContain('my-extra-class');
  });
});
