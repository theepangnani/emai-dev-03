import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { FeatureRows, section } from './FeatureRows';
import { features } from '../content/features';

describe('FeatureRows', () => {
  it('renders all 6 feature rows from the data source', () => {
    const { container } = render(<FeatureRows />);
    const rows = container.querySelectorAll('article.feature-row');
    expect(rows).toHaveLength(6);
    expect(features).toHaveLength(6);
  });

  it('wraps in <section data-landing="v2" class="landing-feature-rows">', () => {
    const { container } = render(<FeatureRows />);
    const wrapper = container.querySelector('section.landing-feature-rows');
    expect(wrapper).not.toBeNull();
    expect(wrapper?.getAttribute('data-landing')).toBe('v2');
  });

  it('renders the §3 intro as the section header (kicker + italicised headline)', () => {
    render(<FeatureRows />);
    expect(screen.getByText(/Introducing ClassBridge/)).toBeInTheDocument();
    const heading = screen.getByRole('heading', { level: 2 });
    expect(heading.textContent).toContain('One platform. Every role.');
    expect(heading.textContent).toContain('Every signal.');
    // Serif-italic accent survives render
    expect(heading.querySelector('em')?.textContent).toBe('Every signal.');
  });

  it('alternates layout: odd rows (2nd, 4th, 6th) get the reversed modifier', () => {
    const { container } = render(<FeatureRows />);
    const rows = Array.from(container.querySelectorAll('article.feature-row'));
    rows.forEach((row, index) => {
      const isReversed = row.classList.contains('feature-row--reversed');
      expect(isReversed).toBe(index % 2 === 1);
    });
  });

  it('renders each row with the variant declared in features.ts', () => {
    const { container } = render(<FeatureRows />);
    const rows = Array.from(container.querySelectorAll('article.feature-row'));
    rows.forEach((row, index) => {
      expect(row.getAttribute('data-variant')).toBe(features[index].variant);
    });
  });

  it('exports a glob-registry section descriptor', () => {
    expect(section.id).toBe('feature-rows');
    expect(section.order).toBe(30);
    expect(section.component).toBe(FeatureRows);
  });
});
