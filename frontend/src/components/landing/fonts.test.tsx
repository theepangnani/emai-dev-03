/**
 * useLandingFonts hook tests (#3873).
 *
 * Guards the invariant that the landing-v2 Google Fonts stylesheet is
 * injected on mount and removed on unmount, so non-landing routes never
 * pay its render-blocking cost. Ref-counting keeps shared usage safe
 * (React StrictMode double-mount in dev, or multiple landing roots).
 */
import { describe, it, expect, afterEach } from 'vitest';
import { render } from '@testing-library/react';
import { useLandingFonts } from './fonts';

function Probe() {
  useLandingFonts();
  return null;
}

describe('useLandingFonts', () => {
  afterEach(() => {
    document.head
      .querySelectorAll('link[data-landing-fonts]')
      .forEach((el) => el.remove());
  });

  it('injects the stylesheet on mount and removes it on unmount', () => {
    expect(
      document.head.querySelector('link[data-landing-fonts]'),
    ).toBeNull();

    const { unmount } = render(<Probe />);

    const link = document.head.querySelector<HTMLLinkElement>(
      'link[data-landing-fonts]',
    );
    expect(link).not.toBeNull();
    expect(link?.rel).toBe('stylesheet');
    expect(link?.href).toContain('fonts.googleapis.com/css2');
    expect(link?.href).toContain('Fraunces');
    expect(link?.href).toContain('Instrument+Sans');

    unmount();

    expect(
      document.head.querySelector('link[data-landing-fonts]'),
    ).toBeNull();
  });

  it('ref-counts across simultaneous mounts so a single instance unmount does not evict a shared <link>', () => {
    const first = render(<Probe />);
    const second = render(<Probe />);

    // One shared link, refs bumped to 2.
    const links = document.head.querySelectorAll(
      'link[data-landing-fonts]',
    );
    expect(links.length).toBe(1);
    expect(links[0].getAttribute('data-refs')).toBe('2');

    // Unmount the second (non-creating) instance — link must survive
    // because the first instance is still mounted.
    second.unmount();
    expect(
      document.head.querySelectorAll('link[data-landing-fonts]').length,
    ).toBe(1);

    // Unmount the original creator — link is removed (created=true branch).
    first.unmount();
    expect(
      document.head.querySelector('link[data-landing-fonts]'),
    ).toBeNull();
  });
});
