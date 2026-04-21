/**
 * SeoDefaults tests — #3874 (CB-LAND-001 fast-follow).
 *
 * Guards the baseline meta/OG/canonical tags so non-landing routes
 * (`/login`, `/dashboard`, etc.) don't inherit landing copy from a stale
 * LandingSeo mount.
 */
import { describe, it, expect, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/react';
import { SeoDefaults, SEO_DEFAULTS } from './SeoDefaults';

afterEach(() => {
  cleanup();
  document
    .querySelectorAll(
      'meta[name="description"], meta[property^="og:"], meta[name^="twitter:"], link[rel="canonical"]',
    )
    .forEach((el) => el.remove());
  document.title = '';
});

describe('SeoDefaults', () => {
  it('sets a generic document.title on mount (not landing copy)', () => {
    render(<SeoDefaults />);

    expect(document.title).toBe(SEO_DEFAULTS.title);
    expect(document.title).not.toMatch(/homework gap/i);
  });

  it('upserts the meta description to the generic ClassBridge default', () => {
    render(<SeoDefaults />);

    const desc = document
      .querySelector<HTMLMetaElement>('meta[name="description"]')
      ?.getAttribute('content');
    expect(desc).toBe(SEO_DEFAULTS.description);
    expect(desc).toMatch(/parents, students, and teachers/i);
  });

  it('sets canonical to the site root URL', () => {
    render(<SeoDefaults />);

    expect(
      document
        .querySelector<HTMLLinkElement>('link[rel="canonical"]')
        ?.getAttribute('href'),
    ).toBe(SEO_DEFAULTS.siteUrl);
  });
});
