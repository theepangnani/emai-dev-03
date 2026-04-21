import { describe, it, expect } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { LandingFooter, section } from './LandingFooter';

function renderFooter() {
  return render(
    <MemoryRouter>
      <LandingFooter />
    </MemoryRouter>,
  );
}

describe('LandingFooter', () => {
  it('renders the four columns: Product / Company / Legal / Connect', () => {
    renderFooter();
    const product = screen.getByRole('heading', { level: 3, name: /^Product$/ });
    const company = screen.getByRole('heading', { level: 3, name: /^Company$/ });
    const legal = screen.getByRole('heading', { level: 3, name: /^Legal$/ });
    const connect = screen.getByRole('heading', { level: 3, name: /^Connect$/ });
    expect(product).toBeInTheDocument();
    expect(company).toBeInTheDocument();
    expect(legal).toBeInTheDocument();
    expect(connect).toBeInTheDocument();
  });

  it('renders the Product column link set', () => {
    renderFooter();
    const col = screen
      .getByRole('heading', { level: 3, name: /^Product$/ })
      .closest('section')!;
    expect(within(col).getByRole('link', { name: /features/i })).toBeInTheDocument();
    expect(within(col).getByRole('link', { name: /how it works/i })).toBeInTheDocument();
    expect(within(col).getByRole('link', { name: /pricing/i })).toBeInTheDocument();
    expect(within(col).getByRole('link', { name: /integrations/i })).toBeInTheDocument();
  });

  it('wires Legal privacy + terms links to the real routes', () => {
    renderFooter();
    const col = screen
      .getByRole('heading', { level: 3, name: /^Legal$/ })
      .closest('section')!;
    expect(within(col).getByRole('link', { name: /privacy/i })).toHaveAttribute(
      'href',
      '/privacy',
    );
    expect(within(col).getByRole('link', { name: /terms/i })).toHaveAttribute(
      'href',
      '/terms',
    );
  });

  it('renders the copyright strip and Made in Canada chip', () => {
    renderFooter();
    expect(
      screen.getByText(/2026 ClassBridge.*classbridge\.ca/i),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/made in canada/i)).toBeInTheDocument();
  });

  it('is a <footer> with data-landing="v2" so S1 tokens resolve', () => {
    const { container } = renderFooter();
    const footer = container.querySelector('footer.landing-footer');
    expect(footer).not.toBeNull();
    expect(footer).toHaveAttribute('data-landing', 'v2');
  });

  it('exports section metadata with order 9999 so it renders last', () => {
    expect(section.id).toBe('footer');
    expect(section.order).toBe(9999);
    expect(section.component).toBe(LandingFooter);
  });
});
