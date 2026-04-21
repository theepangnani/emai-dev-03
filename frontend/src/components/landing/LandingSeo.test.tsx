/**
 * LandingSeo tests — CB-LAND-001 S15 (#3815, §6.136.6).
 *
 * Regression guard on the snapshot/spec contract: after mount,
 * `document.title` matches the spec string and the critical meta /
 * JSON-LD tags are present. If future work swaps out the copy, these
 * tests catch it — update the expected strings deliberately.
 */
import { describe, it, expect, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/react';
import { LandingSeo } from './LandingSeo';
import { SEO_DEFAULTS } from '../SeoDefaults';

afterEach(() => {
  cleanup();
  // Clear any lingering <meta> tags between tests so one run doesn't
  // poison the next. JSON-LD scripts self-clean via the effect cleanup.
  document
    .querySelectorAll(
      'meta[name="description"], meta[property^="og:"], meta[name^="twitter:"], link[rel="canonical"], script[data-landing-seo]',
    )
    .forEach((el) => el.remove());
  document.title = '';
});

describe('LandingSeo', () => {
  it('sets document.title to the CB-LAND-001 S15 spec string after mount', () => {
    render(<LandingSeo />);

    expect(document.title).toBe(
      'ClassBridge — Close the homework gap. Together, in one place.',
    );
  });

  it('upserts the meta description (150-160 chars, composed from §6.136 copy)', () => {
    render(<LandingSeo />);

    const desc = document
      .querySelector<HTMLMetaElement>('meta[name="description"]')
      ?.getAttribute('content');
    expect(desc).toBeTruthy();
    expect(desc!.length).toBeGreaterThanOrEqual(150);
    expect(desc!.length).toBeLessThanOrEqual(160);
    expect(desc).toMatch(/parents, students, and teachers/i);
  });

  it('injects Open Graph and Twitter card meta tags', () => {
    render(<LandingSeo />);

    // OG
    expect(
      document
        .querySelector<HTMLMetaElement>('meta[property="og:title"]')
        ?.getAttribute('content'),
    ).toContain('ClassBridge');
    expect(
      document
        .querySelector<HTMLMetaElement>('meta[property="og:image"]')
        ?.getAttribute('content'),
    ).toMatch(/\/classbridge-hero-logo\.png$/);
    expect(
      document
        .querySelector<HTMLMetaElement>('meta[property="og:type"]')
        ?.getAttribute('content'),
    ).toBe('website');
    expect(
      document
        .querySelector<HTMLMetaElement>('meta[property="og:url"]')
        ?.getAttribute('content'),
    ).toBe('https://www.classbridge.ca');

    // Twitter card — spec demands summary_large_image.
    expect(
      document
        .querySelector<HTMLMetaElement>('meta[name="twitter:card"]')
        ?.getAttribute('content'),
    ).toBe('summary_large_image');
  });

  it('sets <link rel="canonical"> to the root URL', () => {
    render(<LandingSeo />);

    expect(
      document
        .querySelector<HTMLLinkElement>('link[rel="canonical"]')
        ?.getAttribute('href'),
    ).toBe('https://www.classbridge.ca');
  });

  it('injects three JSON-LD blocks (Organization, Product, FAQPage) as valid JSON', () => {
    render(<LandingSeo />);

    const scripts = document.querySelectorAll<HTMLScriptElement>(
      'script[type="application/ld+json"][data-landing-seo]',
    );
    expect(scripts).toHaveLength(3);

    const types = new Set<string>();
    for (const script of scripts) {
      // Must be valid JSON — if this throws, the injected blob is malformed.
      const parsed = JSON.parse(script.text) as { '@type'?: string };
      expect(parsed['@type']).toBeTruthy();
      types.add(parsed['@type']!);
    }

    expect(types).toEqual(new Set(['Organization', 'Product', 'FAQPage']));
  });

  it('cleans up injected JSON-LD blocks on unmount', () => {
    const { unmount } = render(<LandingSeo />);
    expect(
      document.querySelectorAll('script[data-landing-seo]').length,
    ).toBe(3);

    unmount();
    expect(
      document.querySelectorAll('script[data-landing-seo]').length,
    ).toBe(0);
  });

  it('restores the SeoDefaults meta/OG/canonical baseline on unmount (#3874)', () => {
    const { unmount } = render(<LandingSeo />);
    // Sanity — landing copy is active while mounted.
    expect(document.title).toMatch(/homework gap/i);

    unmount();

    // Cleanup should reinstate the generic SeoDefaults values so that
    // routes like /login or /dashboard don't show landing meta.
    expect(document.title).toBe(SEO_DEFAULTS.title);
    expect(
      document
        .querySelector<HTMLMetaElement>('meta[name="description"]')
        ?.getAttribute('content'),
    ).toBe(SEO_DEFAULTS.description);
    expect(
      document
        .querySelector<HTMLMetaElement>('meta[property="og:title"]')
        ?.getAttribute('content'),
    ).toBe(SEO_DEFAULTS.title);
    expect(
      document
        .querySelector<HTMLMetaElement>('meta[property="og:description"]')
        ?.getAttribute('content'),
    ).toBe(SEO_DEFAULTS.description);
    expect(
      document
        .querySelector<HTMLMetaElement>('meta[property="og:image"]')
        ?.getAttribute('content'),
    ).toBe(SEO_DEFAULTS.ogImage);
    expect(
      document
        .querySelector<HTMLLinkElement>('link[rel="canonical"]')
        ?.getAttribute('href'),
    ).toBe(SEO_DEFAULTS.siteUrl);
  });
});
