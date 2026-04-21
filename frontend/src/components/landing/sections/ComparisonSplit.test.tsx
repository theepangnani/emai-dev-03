import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ComparisonSplit, section } from './ComparisonSplit';

describe('ComparisonSplit (CB-LAND-001 S7)', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
      })),
    });
  });

  it('renders the headline with italic "vs"', () => {
    const { container } = render(<ComparisonSplit />);
    const heading = container.querySelector('h2.landing-compare__title');
    expect(heading?.textContent).toBe('The old homework routine vs ClassBridge.');
    expect(heading?.querySelector('em')?.textContent).toBe('vs');
  });

  it('renders both column headers', () => {
    render(<ComparisonSplit />);
    expect(screen.getByRole('heading', { name: 'The Old Way' })).toBeDefined();
    expect(screen.getByRole('heading', { name: 'The ClassBridge Way' })).toBeDefined();
  });

  it('renders 5 old-way pills and 5 new-way pills (5 paired rows)', () => {
    const { container } = render(<ComparisonSplit />);
    const oldPills = container.querySelectorAll('.landing-compare__pill--old');
    const newPills = container.querySelectorAll('.landing-compare__pill--new');
    expect(oldPills.length).toBe(5);
    expect(newPills.length).toBe(5);
  });

  it('renders the expected paired labels', () => {
    render(<ComparisonSplit />);
    const pairs: Array<[string, string]> = [
      ['Scattered Gmail threads', 'Daily AI digest'],
      ['Endless re-reading', 'Flash Tutor'],
      ['Parent out of loop', 'Parent digest'],
      ['Paper scans lost', 'AI study guides'],
      ['One-shot quizzes', 'Adaptive difficulty'],
    ];
    for (const [oldLabel, newLabel] of pairs) {
      expect(screen.getByText(oldLabel)).toBeDefined();
      expect(screen.getByText(newLabel)).toBeDefined();
    }
  });

  it('wraps in a section with data-landing="v2" and class "landing-compare"', () => {
    const { container } = render(<ComparisonSplit />);
    const sectionEl = container.querySelector('section');
    expect(sectionEl).not.toBeNull();
    expect(sectionEl!.getAttribute('data-landing')).toBe('v2');
    expect(sectionEl!.classList.contains('landing-compare')).toBe(true);
  });

  it('renders the DemoMascot between the two columns', () => {
    const { container } = render(<ComparisonSplit />);
    const mascotWrap = container.querySelector('.landing-compare__mascot');
    expect(mascotWrap).not.toBeNull();
    const svg = mascotWrap!.querySelector('svg.demo-mascot');
    expect(svg).not.toBeNull();
    expect(svg!.getAttribute('class')).toContain('demo-mascot--greeting');
  });

  it('exposes a section registry export with id "compare" and order 50', () => {
    expect(section.id).toBe('compare');
    expect(section.order).toBe(50);
    expect(section.component).toBe(ComparisonSplit);
  });
});
