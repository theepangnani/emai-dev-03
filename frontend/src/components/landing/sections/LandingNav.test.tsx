import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// #3889 — mock useFeature so we can exercise both waitlist-on and waitlist-off
// branches of the trailing nav CTA.
const useFeatureMock = vi.fn<(key: string) => boolean>();
vi.mock('../../../hooks/useFeatureToggle', () => ({
  useFeature: (key: string) => useFeatureMock(key),
}));

import { LandingNav, section } from './LandingNav';

function renderNav() {
  return render(
    <MemoryRouter>
      <LandingNav />
    </MemoryRouter>,
  );
}

describe('LandingNav (#3885)', () => {
  beforeEach(() => {
    useFeatureMock.mockReset();
    useFeatureMock.mockReturnValue(true); // default pre-launch posture
  });

  it('renders the ClassBridge logo with non-empty alt text', () => {
    renderNav();
    const logo = screen.getByAltText('ClassBridge');
    expect(logo).toBeInTheDocument();
    expect(logo.tagName).toBe('IMG');
    expect(logo.getAttribute('src')).toBe('/classbridge-logo-v6.png');
  });

  it('wraps the logo in a link to the site root', () => {
    renderNav();
    const brandLink = screen.getByRole('link', { name: /classbridge home/i });
    expect(brandLink).toHaveAttribute('href', '/');
  });

  it('renders a Log In link pointing at /login', () => {
    renderNav();
    const login = screen.getByRole('link', { name: /^log in$/i });
    expect(login).toHaveAttribute('href', '/login');
  });

  it('renders a Join Waitlist link pointing at /waitlist when waitlist_enabled is true', () => {
    renderNav();
    const waitlist = screen.getByRole('link', { name: /join waitlist/i });
    expect(waitlist).toHaveAttribute('href', '/waitlist');
  });

  it('renders a Get Started link pointing at /register when waitlist_enabled is false (#3889)', () => {
    useFeatureMock.mockReturnValue(false);
    renderNav();
    expect(
      screen.queryByRole('link', { name: /join waitlist/i }),
    ).not.toBeInTheDocument();
    const cta = screen.getByRole('link', { name: /get started/i });
    expect(cta).toHaveAttribute('href', '/register');
  });

  it('renders a <nav> landmark with aria-label="Landing navigation" and data-landing="v2"', () => {
    const { container } = renderNav();
    const nav = container.querySelector('nav.landing-nav');
    expect(nav).not.toBeNull();
    expect(nav).toHaveAttribute('aria-label', 'Landing navigation');
    expect(nav).toHaveAttribute('data-landing', 'v2');
  });

  it('exports section metadata with order 5 so it renders before LandingHero', () => {
    expect(section.id).toBe('nav');
    expect(section.order).toBe(5);
    expect(section.component).toBe(LandingNav);
  });
});
