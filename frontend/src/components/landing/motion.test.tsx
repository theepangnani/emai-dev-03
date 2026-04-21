/**
 * CB-LAND-001 S13 — tests for the shared motion hooks (#3813).
 *
 * Covers:
 *   - `usePrefersReducedMotion` reflects the initial matchMedia result and
 *     updates when the media query changes.
 *   - `useScrollReveal` starts hidden, reveals when IntersectionObserver
 *     fires `isIntersecting: true`, and short-circuits to "revealed" when
 *     the user prefers reduced motion (no observer installed).
 *   - A representative landing-v2 section (`ComparisonSplit`) fully honours
 *     the reduced-motion preference — no `.landing-reveal--hidden` class on
 *     its mascot when the media query is `reduce`.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, render, renderHook, screen } from '@testing-library/react';
import { usePrefersReducedMotion, useScrollReveal } from './motion';
import { ComparisonSplit } from './sections/ComparisonSplit';

// ----- matchMedia harness -------------------------------------------------

type Listener = (event: MediaQueryListEvent) => void;

interface FakeMQL {
  matches: boolean;
  media: string;
  onchange: null;
  addEventListener: (type: 'change', listener: Listener) => void;
  removeEventListener: (type: 'change', listener: Listener) => void;
  addListener: (listener: Listener) => void;
  removeListener: (listener: Listener) => void;
  dispatchEvent: () => boolean;
  __fire: (matches: boolean) => void;
}

function installMatchMedia(initialMatches: boolean) {
  const listeners = new Set<Listener>();
  const mql: FakeMQL = {
    matches: initialMatches,
    media: '(prefers-reduced-motion: reduce)',
    onchange: null,
    addEventListener: (_type, listener) => listeners.add(listener),
    removeEventListener: (_type, listener) => listeners.delete(listener),
    addListener: (listener) => listeners.add(listener),
    removeListener: (listener) => listeners.delete(listener),
    dispatchEvent: () => false,
    __fire(matches: boolean) {
      mql.matches = matches;
      const event = { matches, media: mql.media } as MediaQueryListEvent;
      listeners.forEach((l) => l(event));
    },
  };
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: vi.fn(() => mql as unknown as MediaQueryList),
  });
  return mql;
}

// ----- IntersectionObserver harness --------------------------------------

interface FakeIO {
  observe: ReturnType<typeof vi.fn>;
  disconnect: ReturnType<typeof vi.fn>;
  unobserve: ReturnType<typeof vi.fn>;
  __fire: (isIntersecting: boolean) => void;
}

function installIntersectionObserver() {
  const instances: FakeIO[] = [];
  class FakeObserver {
    observe = vi.fn();
    disconnect = vi.fn();
    unobserve = vi.fn();
    private cb: IntersectionObserverCallback;

    constructor(cb: IntersectionObserverCallback) {
      this.cb = cb;
      const self = this as unknown as FakeIO;
      self.__fire = (isIntersecting: boolean) => {
        cb(
          [{ isIntersecting } as IntersectionObserverEntry],
          this as unknown as IntersectionObserver,
        );
      };
      instances.push(self);
    }
  }
  // @ts-expect-error replace DOM IO with our fake for the test run
  window.IntersectionObserver = FakeObserver;
  return {
    instances,
    latest: () => instances[instances.length - 1],
  };
}

// ----- shared harness -----------------------------------------------------

beforeEach(() => {
  installMatchMedia(false);
  installIntersectionObserver();
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ----- usePrefersReducedMotion -------------------------------------------

describe('usePrefersReducedMotion', () => {
  it('returns false when the media query does not match', () => {
    installMatchMedia(false);
    const { result } = renderHook(() => usePrefersReducedMotion());
    expect(result.current).toBe(false);
  });

  it('returns true when the media query matches on mount', () => {
    installMatchMedia(true);
    const { result } = renderHook(() => usePrefersReducedMotion());
    expect(result.current).toBe(true);
  });

  it('updates when the media query changes at runtime', () => {
    const mql = installMatchMedia(false);
    const { result } = renderHook(() => usePrefersReducedMotion());
    expect(result.current).toBe(false);
    act(() => mql.__fire(true));
    expect(result.current).toBe(true);
    act(() => mql.__fire(false));
    expect(result.current).toBe(false);
  });
});

// ----- useScrollReveal ---------------------------------------------------

// Minimal harness component — attaches the ref to a <div> and surfaces the
// reveal state to the DOM so assertions can read it.
function RevealProbe() {
  const { ref, revealed, hidden } = useScrollReveal<HTMLDivElement>();
  return (
    <div
      ref={ref}
      data-testid="probe"
      data-revealed={String(revealed)}
      className={hidden}
    />
  );
}

describe('useScrollReveal', () => {
  it('starts hidden, then reveals when IO fires isIntersecting=true', () => {
    installMatchMedia(false);
    const io = installIntersectionObserver();
    render(<RevealProbe />);

    const node = screen.getByTestId('probe');
    expect(node.getAttribute('data-revealed')).toBe('false');
    expect(node.className).toContain('landing-reveal--hidden');

    // Sanity — the hook's useEffect should have constructed exactly one observer.
    expect(io.instances.length).toBe(1);

    act(() => io.latest().__fire(true));

    expect(node.getAttribute('data-revealed')).toBe('true');
    expect(node.className).not.toContain('landing-reveal--hidden');
  });

  it('disconnects the observer after first reveal (once: true default)', () => {
    installMatchMedia(false);
    const io = installIntersectionObserver();
    render(<RevealProbe />);
    expect(io.instances.length).toBe(1);
    act(() => io.latest().__fire(true));
    expect(io.latest().disconnect).toHaveBeenCalled();
  });

  it('short-circuits to revealed when prefers-reduced-motion: reduce', () => {
    installMatchMedia(true);
    const io = installIntersectionObserver();
    render(<RevealProbe />);
    const node = screen.getByTestId('probe');
    // Reveal flips on as soon as matchMedia's effect runs and flips the
    // preference — the element must never remain in the hidden state once
    // the user prefers reduced motion.
    expect(node.getAttribute('data-revealed')).toBe('true');
    expect(node.className).not.toContain('landing-reveal--hidden');
    // If an observer was created during the initial (pre-preference-resolved)
    // render pass, it must be disconnected once reduced-motion is detected.
    io.instances.forEach((inst) => {
      expect(inst.disconnect).toHaveBeenCalled();
    });
  });
});

// ----- Integration: reduced-motion across a real section ------------------

describe('integration — reduced motion on a real landing-v2 section', () => {
  it('ComparisonSplit mascot is never in the hidden state when reduce matches', () => {
    installMatchMedia(true);
    installIntersectionObserver();
    const { container } = render(<ComparisonSplit />);
    const mascot = container.querySelector('.landing-compare__mascot');
    expect(mascot).not.toBeNull();
    expect(mascot!.className).not.toContain('landing-reveal--hidden');
  });

  it('ComparisonSplit mascot starts hidden under normal motion and IO revelation flips it', () => {
    installMatchMedia(false);
    const io = installIntersectionObserver();
    const { container } = render(<ComparisonSplit />);
    const mascot = container.querySelector('.landing-compare__mascot')!;
    expect(mascot.className).toContain('landing-reveal--hidden');
    act(() => io.latest().__fire(true));
    expect(mascot.className).not.toContain('landing-reveal--hidden');
  });
});
