import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import { DemoMascot } from './DemoMascot';

describe('DemoMascot', () => {
  beforeEach(() => {
    // Reset matchMedia to "not reduced" before each test
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

  it('renders an SVG with the default size of 48', () => {
    const { container } = render(<DemoMascot />);
    const svg = container.querySelector('svg');
    expect(svg).not.toBeNull();
    expect(svg!.getAttribute('width')).toBe('48');
    expect(svg!.getAttribute('height')).toBe('48');
  });

  it('respects a custom size', () => {
    const { container } = render(<DemoMascot size={96} />);
    const svg = container.querySelector('svg');
    expect(svg!.getAttribute('width')).toBe('96');
    expect(svg!.getAttribute('height')).toBe('96');
  });

  it('defaults to the greeting mood class', () => {
    const { container } = render(<DemoMascot />);
    const svg = container.querySelector('svg');
    expect(svg!.getAttribute('class')).toContain('demo-mascot--greeting');
  });

  it.each(['greeting', 'thinking', 'streaming', 'complete'] as const)(
    'applies the %s mood class',
    (mood) => {
      const { container } = render(<DemoMascot mood={mood} />);
      const svg = container.querySelector('svg');
      expect(svg!.getAttribute('class')).toContain(`demo-mascot--${mood}`);
    },
  );

  it('is marked aria-hidden for decorative use', () => {
    const { container } = render(<DemoMascot />);
    const svg = container.querySelector('svg');
    expect(svg!.getAttribute('aria-hidden')).toBe('true');
  });

  it('applies a user-supplied className', () => {
    const { container } = render(<DemoMascot className="custom-class" />);
    const svg = container.querySelector('svg');
    expect(svg!.getAttribute('class')).toContain('custom-class');
  });

  it('adds the reduced-motion class when prefers-reduced-motion is set', () => {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn((query: string) => ({
        matches: query.includes('reduce'),
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
      })),
    });
    const { container } = render(<DemoMascot />);
    const svg = container.querySelector('svg');
    expect(svg!.getAttribute('class')).toContain('demo-mascot--reduced-motion');
  });

  it('renders a sparkle group only in the complete mood', () => {
    const { container: greetingC } = render(<DemoMascot mood="greeting" />);
    expect(greetingC.querySelector('.demo-mascot__sparkle')).toBeNull();

    const { container: completeC } = render(<DemoMascot mood="complete" />);
    expect(completeC.querySelector('.demo-mascot__sparkle')).not.toBeNull();
  });
});
