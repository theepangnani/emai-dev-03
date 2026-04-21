/**
 * LandingSeo — CB-LAND-001 S15 (#3815, §6.136.6).
 *
 * Injects meta tags + JSON-LD structured data into <head> when the
 * LandingPageV2 route is rendered. This component does NOT render any
 * visible DOM; it's a one-shot `useEffect` that mutates `document`.
 *
 * Why not `react-helmet-async`? That package isn't in the dependency
 * tree and S15 is scoped to "SEO overlay — no new deps". A fast-follow
 * issue (CB-LAND-001-fast-follow: add react-helmet-async) will swap the
 * `useEffect` approach for a provider-based one when the dep lands.
 *
 * Behavior
 * --------
 * On mount:
 *   - Sets `document.title`.
 *   - Upserts `<meta name=description>`, OG tags, Twitter card tags, and
 *     `<link rel=canonical>`.
 *   - Injects one `<script type="application/ld+json">` per structured-
 *     data blob (Organization, Product, FAQPage).
 *
 * On unmount:
 *   - Removes the JSON-LD scripts it owns (tagged via `data-landing-seo`).
 *   - Leaves the meta tags in place — they're harmless on any route and
 *     removing them would cause a flash of empty `<head>` during client-
 *     side navigation.
 *
 * The component is intentionally synchronous/effect-based so there's no
 * visible output for tests to chase through `<Suspense>`. Tests assert
 * on `document.title` / `document.querySelector('meta[...]')` directly.
 */
import { useEffect } from 'react';

/** Stable id used to recognise and clean up our injected JSON-LD blocks. */
const SEO_SCRIPT_ATTR = 'data-landing-seo';

/** Upsert a `<meta>` tag — creates one if missing, else sets `content`. */
function setMeta(attr: 'name' | 'property', key: string, content: string) {
  let el = document.head.querySelector<HTMLMetaElement>(
    `meta[${attr}="${key}"]`,
  );
  if (!el) {
    el = document.createElement('meta');
    el.setAttribute(attr, key);
    document.head.appendChild(el);
  }
  el.setAttribute('content', content);
}

/** Upsert `<link rel=canonical>` to the canonical URL of the landing page. */
function setCanonical(href: string) {
  let el = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
  if (!el) {
    el = document.createElement('link');
    el.setAttribute('rel', 'canonical');
    document.head.appendChild(el);
  }
  el.setAttribute('href', href);
}

/** Inject a JSON-LD block, tagged so we can clean it up on unmount. */
function injectJsonLd(blob: Record<string, unknown>): HTMLScriptElement {
  const script = document.createElement('script');
  script.type = 'application/ld+json';
  script.setAttribute(SEO_SCRIPT_ATTR, '');
  script.text = JSON.stringify(blob);
  document.head.appendChild(script);
  return script;
}

/** Canonical URL for the landing page. */
const SITE_URL = 'https://www.classbridge.ca';
const OG_IMAGE = `${SITE_URL}/og-image.png`;

const TITLE =
  'ClassBridge — Close the homework gap. Together, in one place.';

/**
 * 150-160 char meta description composed from §6.136 intro copy.
 * Measured: 155 chars.
 */
const DESCRIPTION =
  'One calm platform for Ontario parents, students, and teachers — AI study tools, Google Classroom sync, and weekly digests so nobody falls behind this week.';

/** Organization structured-data — identifies ClassBridge to search engines. */
const ORGANIZATION_LD: Record<string, unknown> = {
  '@context': 'https://schema.org',
  '@type': 'Organization',
  name: 'ClassBridge',
  url: SITE_URL,
  logo: `${SITE_URL}/classbridge-logo.png`,
  // sameAs stubs — swap to real handles once social accounts are live.
  sameAs: [
    'https://twitter.com/classbridgeca',
    'https://www.linkedin.com/company/classbridge',
  ],
};

/**
 * Product structured-data — mirrors S11 (PricingTeaser) tier copy so
 * search results stay consistent with the on-page pricing band.
 */
const PRODUCT_LD: Record<string, unknown> = {
  '@context': 'https://schema.org',
  '@type': 'Product',
  name: 'ClassBridge',
  description:
    'AI-powered education platform for Ontario families — parents, students, and teachers share one calm view of the school week.',
  brand: { '@type': 'Brand', name: 'ClassBridge' },
  offers: [
    {
      '@type': 'Offer',
      name: 'Free',
      price: '0',
      priceCurrency: 'CAD',
      description: 'During waitlist. AI usage limits apply.',
      url: `${SITE_URL}/waitlist`,
    },
    {
      '@type': 'Offer',
      name: 'Family',
      price: '9.99',
      priceCurrency: 'CAD',
      description: 'Monthly plan for households — unlimited AI study tools.',
      url: `${SITE_URL}/waitlist`,
    },
    {
      '@type': 'Offer',
      name: 'School Board',
      description: 'Partnership pricing for districts — contact for quote.',
      url: 'mailto:partners@classbridge.ca',
    },
  ],
};

/**
 * FAQPage structured-data — curated 5-10 Q&A.
 *
 * Copying content directly from `pages/FAQPage.tsx` is fragile (that page
 * reads from `/api/faq` at runtime — no static fixture). A fast-follow
 * will wire this to a build-time JSON export of top FAQs.
 */
const FAQPAGE_LD: Record<string, unknown> = {
  '@context': 'https://schema.org',
  '@type': 'FAQPage',
  mainEntity: [
    {
      '@type': 'Question',
      name: 'What is ClassBridge?',
      acceptedAnswer: {
        '@type': 'Answer',
        text: 'ClassBridge is an AI-powered platform that gives parents, students, and teachers a single calm view of the school week — assignments, grades, messages, and AI study tools in one place.',
      },
    },
    {
      '@type': 'Question',
      name: 'Does ClassBridge connect to Google Classroom?',
      acceptedAnswer: {
        '@type': 'Answer',
        text: 'Yes. ClassBridge syncs assignments, announcements, and grades directly from Google Classroom so parents see the same week the teacher posted.',
      },
    },
    {
      '@type': 'Question',
      name: 'Is ClassBridge free?',
      acceptedAnswer: {
        '@type': 'Answer',
        text: 'Yes — ClassBridge is free while you are on the waitlist, with daily AI usage limits. Paid Family and School Board plans are available when you are ready to unlock every study tool.',
      },
    },
    {
      '@type': 'Question',
      name: 'Which Ontario school boards work with ClassBridge?',
      acceptedAnswer: {
        '@type': 'Answer',
        text: 'ClassBridge is built for Ontario families and works alongside boards including YRDSB, TDSB, DDSB, PDSB, and OCDSB. Board partnership discussions are welcome at partners@classbridge.ca.',
      },
    },
    {
      '@type': 'Question',
      name: 'Is student data safe?',
      acceptedAnswer: {
        '@type': 'Answer',
        text: 'ClassBridge follows Ontario privacy rules (MFIPPA/FIPPA) and stores data in Canada. Parents and students control what is shared and can export or delete their data at any time.',
      },
    },
    {
      '@type': 'Question',
      name: 'Can I try ClassBridge before signing up?',
      acceptedAnswer: {
        '@type': 'Answer',
        text: 'Yes — there is a 30-second demo on the home page that shows the student, parent, and teacher views without needing an account.',
      },
    },
    {
      '@type': 'Question',
      name: 'Does ClassBridge replace my teacher or board app?',
      acceptedAnswer: {
        '@type': 'Answer',
        text: 'No — ClassBridge complements existing school tools. It consolidates what is already there and adds AI study help, so parents and students are not juggling five apps and a stack of emails.',
      },
    },
  ],
};

export function LandingSeo() {
  useEffect(() => {
    // Title + base description.
    const prevTitle = document.title;
    document.title = TITLE;

    setMeta('name', 'description', DESCRIPTION);

    // Open Graph — drives link-unfurl on Facebook, LinkedIn, iMessage, etc.
    setMeta('property', 'og:title', TITLE);
    setMeta('property', 'og:description', DESCRIPTION);
    setMeta('property', 'og:image', OG_IMAGE);
    setMeta('property', 'og:url', SITE_URL);
    setMeta('property', 'og:type', 'website');
    setMeta('property', 'og:site_name', 'ClassBridge');

    // Twitter card — large-image variant per spec.
    setMeta('name', 'twitter:card', 'summary_large_image');
    setMeta('name', 'twitter:title', TITLE);
    setMeta('name', 'twitter:description', DESCRIPTION);
    setMeta('name', 'twitter:image', OG_IMAGE);

    // Canonical — prevents duplicate-content penalties for / vs /?utm=…
    setCanonical(SITE_URL);

    // JSON-LD. Inject three separate <script> blocks (Google's recommended
    // pattern — keeps each schema focused and validates independently).
    const organizationScript = injectJsonLd(ORGANIZATION_LD);
    const productScript = injectJsonLd(PRODUCT_LD);
    const faqScript = injectJsonLd(FAQPAGE_LD);

    return () => {
      // Leave meta in place (harmless on other routes) but clean up our
      // JSON-LD so a subsequent route doesn't carry stale structured data.
      organizationScript.remove();
      productScript.remove();
      faqScript.remove();
      // Only restore the prior title if nothing else has claimed it in
      // between. In React 18+ concurrent mode the NEXT route's mount
      // effects may run BEFORE our unmount cleanup — if they already set
      // their own title, we must not stomp on it here.
      if (document.title === TITLE) {
        document.title = prevTitle;
      }
    };
  }, []);

  return null;
}

export default LandingSeo;
