import { render } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { XpStreakBadge } from './XpStreakBadge';

/**
 * Helper — install a window.matchMedia stub that answers "reduce" for
 * prefers-reduced-motion queries and "no-match" for everything else.
 */
function mockReducedMotion(reduce: boolean) {
  const mm = vi.fn().mockImplementation((query: string) => ({
    matches: reduce && query.includes('prefers-reduced-motion: reduce'),
    media: query,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
    onchange: null,
  }));
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: mm,
  });
  return mm;
}

describe('XpStreakBadge accessibility (#4027)', () => {
  afterEach(() => {
    // Restore any matchMedia stub between tests.
    vi.restoreAllMocks();
  });

  it('aria-live appears on hidden sr-only span, not on the visible ticker', () => {
    mockReducedMotion(false);
    const { container } = render(<XpStreakBadge xp={125} streak={3} />);

    // Root must NOT carry aria-live anymore.
    const root = container.querySelector('.xp-streak-badge');
    expect(root).not.toBeNull();
    expect(root?.getAttribute('aria-live')).toBeNull();

    // Visible ticker block must be aria-hidden so AT doesn't see per-tick noise.
    const xpBlock = container.querySelector('.xp-streak-badge__xp');
    expect(xpBlock?.getAttribute('aria-hidden')).toBe('true');

    // The sr-only sibling carries the announcement.
    const live = container.querySelector('.sr-only');
    expect(live).not.toBeNull();
    expect(live?.getAttribute('aria-live')).toBe('polite');
    expect(live?.getAttribute('aria-atomic')).toBe('true');
    expect(live?.textContent).toBe('125 XP, 3 day streak');
  });

  it('sr-only announcement omits streak clause when streak<2', () => {
    mockReducedMotion(false);
    const { container } = render(<XpStreakBadge xp={42} streak={1} />);
    const live = container.querySelector('.sr-only');
    expect(live?.textContent).toBe('42 XP');
  });

  it('streak div uses aria-label (not title)', () => {
    mockReducedMotion(false);
    const { container } = render(<XpStreakBadge xp={10} streak={5} />);
    const streak = container.querySelector('.xp-streak-badge__streak');
    expect(streak).not.toBeNull();
    expect(streak?.getAttribute('aria-label')).toBe('5 day streak');
    expect(streak?.getAttribute('title')).toBeNull();
  });

  it('prefers-reduced-motion: snaps to final value immediately without pulse', () => {
    mockReducedMotion(true);
    // Increase xp from 10 → 40 on re-render; reduced motion should skip ticker + pulse.
    const { container, rerender } = render(<XpStreakBadge xp={10} streak={0} />);
    rerender(<XpStreakBadge xp={40} streak={0} />);

    const xpValue = container.querySelector('.xp-streak-badge__xp-value');
    // Immediate jump — no intermediate tick values.
    expect(xpValue?.textContent).toBe('40');

    // No pulse class applied under reduced motion.
    const xpBlock = container.querySelector('.xp-streak-badge__xp');
    expect(xpBlock?.className).not.toContain('xp-streak-badge__xp--pulse');
  });
});
