/**
 * CB-LAND-001 — landing-v2 Google Fonts loader (#3873).
 *
 * The Fraunces italic + Instrument Sans stylesheet is only used under
 * `[data-landing="v2"]` (the `/` landing route). Loading it render-blocking
 * from `index.html` cost every other route 80-160 KB + one extra blocking
 * request on first paint. This hook scopes that cost to the landing route by
 * injecting the stylesheet `<link>` on mount and removing it on unmount.
 *
 * Idempotent: if the component mounts twice (e.g. React 19 StrictMode double
 * mount in dev, or multiple landing instances), a ref count on the existing
 * `<link>` prevents duplicate network requests and keeps removal safe.
 */
import { useEffect } from 'react';

export const LANDING_FONTS_HREF =
  'https://fonts.googleapis.com/css2?family=Fraunces:ital,wght@1,400;1,500&family=Instrument+Sans:wght@400;500;600&display=swap';

// We key the lookup off `data-landing-fonts` rather than an [href="…"]
// attribute selector. The landing-v2 href contains `;` `,` and `:` which
// some CSS attribute-selector parsers (incl. jsdom) reject, and we only
// ever inject one flavour of this tag, so the data attribute is both
// sufficient and reliable.
const SELECTOR = 'link[data-landing-fonts]';

export function useLandingFonts(): void {
  useEffect(() => {
    let link = document.head.querySelector<HTMLLinkElement>(SELECTOR);
    let created = false;
    if (!link) {
      link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = LANDING_FONTS_HREF;
      link.setAttribute('data-landing-fonts', '1');
      link.setAttribute('data-refs', '1');
      document.head.appendChild(link);
      created = true;
    } else {
      const refs = Number(link.getAttribute('data-refs') ?? '0') + 1;
      link.setAttribute('data-refs', String(refs));
    }
    return () => {
      const cur = document.head.querySelector<HTMLLinkElement>(SELECTOR);
      if (!cur) return;
      const refs = Number(cur.getAttribute('data-refs') ?? '0') - 1;
      if (refs <= 0 || created) {
        cur.remove();
      } else {
        cur.setAttribute('data-refs', String(refs));
      }
    };
  }, []);
}
