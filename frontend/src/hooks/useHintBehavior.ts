import { useEffect, useRef } from "react";

/**
 * Tracks hint display timing for auto-dismiss behavior.
 * If user navigates away within 2 seconds, auto-dismiss the hint.
 * If 2 seconds pass, the hint stays (user is considered engaged).
 *
 * @param hintKey  - current hint key (null = no hint showing)
 * @param dismissFn - function to call when auto-dismissing
 */
export function useHintAutoDismiss(
  hintKey: string | null,
  dismissFn: (() => Promise<void>) | null
): void {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const engagedRef = useRef(false);
  const dismissRef = useRef(dismissFn);

  // Keep dismiss function ref current to avoid stale closures
  useEffect(() => {
    dismissRef.current = dismissFn;
  }, [dismissFn]);

  useEffect(() => {
    // Reset engagement flag when hint changes
    engagedRef.current = false;

    if (!hintKey) {
      return;
    }

    // Start 2-second timer — if it fires, user is engaged
    timerRef.current = setTimeout(() => {
      engagedRef.current = true;
      timerRef.current = null;
    }, 2000);

    // Cleanup: if component unmounts (navigation) before 2s, auto-dismiss
    return () => {
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current);
        timerRef.current = null;

        // User left before 2s — auto-dismiss
        if (!engagedRef.current && dismissRef.current) {
          dismissRef.current().catch(() => {
            // Silently ignore dismiss errors during unmount
          });
        }
      }
    };
  }, [hintKey]);
}
