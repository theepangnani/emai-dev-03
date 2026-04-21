/**
 * CB-LAND-001 S16 — `useSectionViewTracker`.
 *
 * Fires `landing_v2.section_view` exactly once per component mount,
 * the first time the attached element crosses 50% of the viewport.
 *
 * Caller pattern:
 *
 *     const ref = useSectionViewTracker('hero');
 *     return <section ref={ref} …>…</section>;
 *
 * IntersectionObserver is unavailable in older jsdom / SSR paths — the
 * hook degrades to a silent no-op there rather than throwing. Cleanup
 * disconnects the observer on unmount.
 *
 * Note: S13 (motion / scroll reveal) is not yet on main, so there is
 * no `useScrollReveal` to compose with; if that hook lands later the
 * two can share a single observer via a small util without changing
 * the public signature here.
 */

import { useEffect, useRef } from 'react';
import { emitSectionView } from './analytics';

export function useSectionViewTracker<T extends Element = HTMLElement>(
  sectionId: string,
) {
  const ref = useRef<T | null>(null);
  const firedRef = useRef(false);

  useEffect(() => {
    if (firedRef.current) return;
    if (typeof window === 'undefined') return;
    if (typeof IntersectionObserver === 'undefined') return;
    const node = ref.current;
    if (!node) return;

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          if (entry.intersectionRatio < 0.5) continue;
          if (firedRef.current) continue;
          firedRef.current = true;
          emitSectionView(sectionId);
          observer.disconnect();
          break;
        }
      },
      { threshold: 0.5 },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [sectionId]);

  return ref;
}
