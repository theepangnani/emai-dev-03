/**
 * CB-LAND-001 S13 — shared motion primitives for landing v2 (#3813).
 *
 * Two tiny, SSR-safe hooks used by every landing-v2 section to express
 * "appear on scroll" entrance and to honour user motion preferences.
 * Motion tokens (`--motion-spring-fast`, `--motion-spring-slow`,
 * `--motion-scanline-loop`) are defined under `[data-landing="v2"]` in
 * `frontend/src/index.css` and are zeroed automatically by the S1 reduced-
 * motion contract (`@media (prefers-reduced-motion: reduce)`).
 *
 * These hooks never read the tokens directly — they only toggle a class or
 * expose the reduced-motion boolean so components can opt-out of JS-driven
 * motion entirely (e.g. skipping a one-shot bounce when the user prefers
 * reduced motion). This keeps the motion contract single-sourced in CSS
 * per §6.136.5.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

type RevealTarget = HTMLElement | null;

const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)';

function getMatchMedia(): ((q: string) => MediaQueryList) | null {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return null;
  }
  return (q) => window.matchMedia(q);
}

/**
 * `usePrefersReducedMotion` — reactive wrapper around
 * `matchMedia('(prefers-reduced-motion: reduce)')`.
 *
 * SSR-safe: returns `false` during server render (no `window`) and during the
 * first client render, then subscribes in `useEffect`. The CSS layer is the
 * authoritative reduced-motion gate (via the zeroed motion tokens); this hook
 * exists for the narrow cases where we must NOT fire a JS-driven one-shot
 * animation at all (vs. just running it at 0ms).
 */
export function usePrefersReducedMotion(): boolean {
  // Lazy initializer reads matchMedia once on first client render so we never
  // cascade a setState-in-effect on mount. SSR returns `false` (no window).
  const [reduced, setReduced] = useState<boolean>(() => {
    const mm = getMatchMedia();
    if (!mm) return false;
    return mm(REDUCED_MOTION_QUERY).matches;
  });

  useEffect(() => {
    const mm = getMatchMedia();
    if (!mm) return;

    const mql = mm(REDUCED_MOTION_QUERY);
    const onChange = (event: MediaQueryListEvent) => setReduced(event.matches);

    // Subscribe only — the lazy initializer already captured `mql.matches`
    // for the initial render, and `onChange` handles every subsequent flip.
    mql.addEventListener('change', onChange);
    return () => mql.removeEventListener('change', onChange);
  }, []);

  return reduced;
}

export interface UseScrollRevealOptions {
  /** Viewport fraction that must be visible before reveal fires. Default `0.12`. */
  threshold?: number;
  /** `rootMargin` forwarded to the IntersectionObserver. Default `'0px 0px -8% 0px'`. */
  rootMargin?: string;
  /** Only reveal once, then disconnect. Default `true`. */
  once?: boolean;
  /**
   * Start in the revealed state (skip the hidden → rest transition). Used when
   * the target is a deep-link / hash anchor (e.g. `/#pricing`) so the browser's
   * scroll-to-anchor doesn't land on a hidden element that never re-fires IO.
   * Default `false`.
   */
  initiallyRevealed?: boolean;
}

export interface UseScrollRevealResult<T extends HTMLElement = HTMLElement> {
  /** Ref to attach to the element you want revealed. */
  ref: (node: T | null) => void;
  /** `true` once the element has crossed the threshold (or immediately if reduced-motion). */
  revealed: boolean;
  /** Stable className string — present when NOT yet revealed, empty once revealed.
   *  Apply like `className={\`my-section \${hidden}\`}`. */
  hidden: string;
}

/**
 * `useScrollReveal` — IntersectionObserver-driven entrance reveal.
 *
 * Returns a ref callback + a `hidden` className that the caller composes onto
 * the element they want animated. When the element intersects the viewport,
 * the hook flips `revealed` to `true` and the `hidden` string becomes empty —
 * so the element transitions from its "hidden" state (opacity 0 + 16px Y
 * offset) to rest using `var(--motion-spring-slow)` (see `motion.css`).
 *
 * Design choices:
 *   - Adds the pre-reveal class rather than a post-reveal class so SSR / no-JS
 *     renders the final, visible state (progressive enhancement).
 *   - Reduced-motion short-circuits: `revealed` starts `true`, the hook
 *     never installs an observer, and `hidden` is always empty.
 *   - `once` disconnects the observer the first time the element enters
 *     view so re-scrolls don't re-fire the transition.
 *   - SSR-safe: no `window` / `IntersectionObserver` access outside `useEffect`.
 */
export function useScrollReveal<T extends HTMLElement = HTMLElement>(
  options: UseScrollRevealOptions = {},
): UseScrollRevealResult<T> {
  const {
    threshold = 0.12,
    rootMargin = '0px 0px -8% 0px',
    once = true,
    initiallyRevealed = false,
  } = options;

  const prefersReduced = usePrefersReducedMotion();
  const hasIO =
    typeof window !== 'undefined' && typeof window.IntersectionObserver !== 'undefined';
  // `intersected` tracks the IO-driven part of the story (did the element
  // enter the viewport?). The returned `revealed` value is derived below —
  // it's forced to `true` under reduced-motion or when IO is unavailable so
  // we never need to setState-in-effect to flip modes.
  const [intersected, setIntersected] = useState<boolean>(initiallyRevealed);
  const nodeRef = useRef<RevealTarget>(null);
  const observedRef = useRef<RevealTarget>(null);
  const observerRef = useRef<IntersectionObserver | null>(null);

  useEffect(() => {
    if (prefersReduced || !hasIO) {
      // Reduced-motion or no IO: reveal is derived to `true`, no observer needed.
      return;
    }

    const node = nodeRef.current;
    if (!node) return;

    const observer = new window.IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setIntersected(true);
            if (once) {
              observer.disconnect();
              observerRef.current = null;
              observedRef.current = null;
            }
          } else if (!once) {
            setIntersected(false);
          }
        }
      },
      { threshold, rootMargin },
    );
    observer.observe(node);
    observerRef.current = observer;
    observedRef.current = node;

    return () => {
      observer.disconnect();
      observerRef.current = null;
      observedRef.current = null;
    };
    // Re-run if the reduced-motion preference changes or options mutate.
  }, [prefersReduced, hasIO, threshold, rootMargin, once]);

  // Stable ref callback: React invokes ref callbacks on every render when the
  // callback identity changes, which would otherwise re-observe an unchanged
  // node each render. `useCallback([])` pins identity; `observedRef` dedupes
  // repeat observations of the same node and unobserves the previous one when
  // the node swaps (remount / key change).
  const ref = useCallback((node: T | null) => {
    const obs = observerRef.current;
    if (observedRef.current && observedRef.current !== node && obs) {
      obs.unobserve(observedRef.current);
    }
    nodeRef.current = node;
    observedRef.current = node;
    if (node && obs) obs.observe(node);
  }, []);

  // Derive the public `revealed` flag so runtime transitions between reduced-
  // motion / no-IO / intersection states never require setState-in-effect.
  const revealed = intersected || prefersReduced || !hasIO;

  return {
    ref,
    revealed,
    hidden: revealed ? '' : 'landing-reveal landing-reveal--hidden',
  };
}
