/**
 * SeoDefaults — generic meta tags for any non-landing route.
 *
 * Mounted once at the top of App. Sets baseline <title>, description,
 * canonical, OG, and Twitter tags so that routes other than `/` don't
 * inherit landing copy from a stale LandingSeo mount (#3874).
 *
 * LandingSeo (on /) overwrites these on mount and lets them revert on
 * unmount — restoring the DefaultSeo baseline.
 */
import { useEffect } from 'react';

const SITE_URL = 'https://www.classbridge.ca';
const DEFAULT_TITLE =
  'ClassBridge — AI-powered education platform for Ontario families';
const DEFAULT_DESCRIPTION =
  'ClassBridge gives parents, students, and teachers one calm view of the school week — AI study tools, Google Classroom sync, weekly digests.';
const DEFAULT_OG_IMAGE = `${SITE_URL}/classbridge-hero-logo.png`;

/**
 * Baseline values LandingSeo re-applies on unmount so non-landing routes
 * don't keep the landing meta/OG/canonical tags. Exported so the two
 * components stay in sync from a single source of truth.
 */
export const SEO_DEFAULTS = {
  siteUrl: SITE_URL,
  title: DEFAULT_TITLE,
  description: DEFAULT_DESCRIPTION,
  ogImage: DEFAULT_OG_IMAGE,
} as const;

/** Upsert a `<meta>` tag — creates one if missing, else sets `content`. */
export function setMeta(
  attr: 'name' | 'property',
  key: string,
  content: string,
) {
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

/** Upsert `<link rel=canonical>` to the given href. */
export function setCanonical(href: string) {
  let el = document.head.querySelector<HTMLLinkElement>(
    'link[rel="canonical"]',
  );
  if (!el) {
    el = document.createElement('link');
    el.setAttribute('rel', 'canonical');
    document.head.appendChild(el);
  }
  el.setAttribute('href', href);
}

/**
 * Apply the SeoDefaults baseline to the document head. Shared by
 * SeoDefaults on mount and LandingSeo on unmount so the two paths
 * produce identical output.
 */
export function applySeoDefaults() {
  document.title = SEO_DEFAULTS.title;
  setMeta('name', 'description', SEO_DEFAULTS.description);
  setMeta('property', 'og:title', SEO_DEFAULTS.title);
  setMeta('property', 'og:description', SEO_DEFAULTS.description);
  setMeta('property', 'og:image', SEO_DEFAULTS.ogImage);
  setMeta('property', 'og:url', SEO_DEFAULTS.siteUrl);
  setMeta('property', 'og:type', 'website');
  setMeta('property', 'og:site_name', 'ClassBridge');
  setMeta('name', 'twitter:card', 'summary_large_image');
  setMeta('name', 'twitter:title', SEO_DEFAULTS.title);
  setMeta('name', 'twitter:description', SEO_DEFAULTS.description);
  setMeta('name', 'twitter:image', SEO_DEFAULTS.ogImage);
  setCanonical(SEO_DEFAULTS.siteUrl);
}

export function SeoDefaults() {
  useEffect(() => {
    applySeoDefaults();
  }, []);
  return null;
}

export default SeoDefaults;
