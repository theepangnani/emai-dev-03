/**
 * CB-BRIDGE-001 — Bridge re-skin Google Fonts loader (#4105).
 *
 * Mirrors the landing-v2 fonts pattern (`components/landing/fonts.ts`):
 * stylesheet is injected on mount and removed on unmount so the cost is
 * scoped to routes that opt in. Ref-counted to be safe under React 19
 * StrictMode double-mount and concurrent consumers.
 */
import { useEffect } from 'react';

export const BRIDGE_FONTS_HREF =
  'https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,400;0,9..144,500;0,9..144,600;1,9..144,300;1,9..144,400&family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700&family=JetBrains+Mono:wght@400;500&display=swap';

const SELECTOR = 'link[data-bridge-fonts]';

export function useBridgeFonts(): void {
  useEffect(() => {
    let link = document.head.querySelector<HTMLLinkElement>(SELECTOR);
    if (!link) {
      link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = BRIDGE_FONTS_HREF;
      link.setAttribute('data-bridge-fonts', '1');
      link.setAttribute('data-refs', '1');
      document.head.appendChild(link);
    } else {
      const refs = Number(link.getAttribute('data-refs') ?? '0') + 1;
      link.setAttribute('data-refs', String(refs));
    }
    return () => {
      const cur = document.head.querySelector<HTMLLinkElement>(SELECTOR);
      if (!cur) return;
      const refs = Number(cur.getAttribute('data-refs') ?? '0') - 1;
      if (refs <= 0) {
        cur.remove();
      } else {
        cur.setAttribute('data-refs', String(refs));
      }
    };
  }, []);
}
