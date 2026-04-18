import { useEffect, useState } from 'react';

export const BEAT_INTERVAL_MS = 600;

/**
 * Returns the indices of beats that should currently be visible.
 * In reduced-motion mode, all beats are returned immediately.
 * Otherwise beats reveal one-at-a-time on a 600ms interval.
 */
export function useTuesdayMirrorAnimation(
  totalBeats: number,
  reducedMotion: boolean,
): number[] {
  const [visibleCount, setVisibleCount] = useState<number>(() =>
    reducedMotion ? totalBeats : totalBeats > 0 ? 1 : 0,
  );

  useEffect(() => {
    if (reducedMotion) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: sync visible count to totalBeats when content arrives
      setVisibleCount(totalBeats);
      return;
    }
    setVisibleCount(totalBeats > 0 ? 1 : 0);
    if (totalBeats <= 1) return;

    let current = 1;
    const id = window.setInterval(() => {
      current += 1;
      setVisibleCount(current);
      if (current >= totalBeats) {
        window.clearInterval(id);
      }
    }, BEAT_INTERVAL_MS);

    return () => window.clearInterval(id);
  }, [totalBeats, reducedMotion]);

  const visible: number[] = [];
  for (let i = 0; i < visibleCount; i += 1) visible.push(i);
  return visible;
}
