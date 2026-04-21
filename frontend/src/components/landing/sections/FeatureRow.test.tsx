import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { FeatureRow } from './FeatureRow';
import type { FeatureRowContent, FeatureRowVariant } from '../content/features';

const makeContent = (variant: FeatureRowVariant): FeatureRowContent => ({
  id: `row-${variant}`,
  kicker: 'Test Kicker',
  headlineHtml: 'Notes that <em>write themselves.</em>',
  body: 'Three-line body copy used to verify the feature row renders correctly.',
  learnMoreLabel: 'Learn more',
  screenshotLabel: `Screenshot: ${variant} demo`,
  variant,
});

describe('FeatureRow', () => {
  const variants: FeatureRowVariant[] = ['peach', 'mint', 'lavender', 'pink'];

  variants.forEach((variant) => {
    it(`renders for the ${variant} variant with all authoring fields`, () => {
      const content = makeContent(variant);
      const { container } = render(<FeatureRow content={content} />);

      // Variant-driven class + data attribute
      const article = container.querySelector('article.feature-row');
      expect(article).not.toBeNull();
      expect(article?.classList.contains(`feature-row--${variant}`)).toBe(true);
      expect(article?.getAttribute('data-variant')).toBe(variant);

      // Kicker, body, learn-more label
      expect(screen.getByText('Test Kicker')).toBeInTheDocument();
      expect(screen.getByText(/Three-line body copy/)).toBeInTheDocument();
      expect(screen.getByText(/Learn more/)).toBeInTheDocument();

      // Headline serif-italic <em> accent preserved via dangerouslySetInnerHTML
      const headline = container.querySelector('.feature-row__headline');
      expect(headline?.innerHTML).toContain('<em>write themselves.</em>');

      // Mockup exposes the screenshot label as aria-label (role=img)
      const mockup = screen.getByRole('img', { name: `Screenshot: ${variant} demo` });
      expect(mockup).toBeInTheDocument();
    });
  });

  it('applies the reversed modifier class when reversed=true', () => {
    const { container } = render(
      <FeatureRow content={makeContent('peach')} reversed />,
    );
    const article = container.querySelector('article.feature-row');
    expect(article?.classList.contains('feature-row--reversed')).toBe(true);
  });

  it('does not apply the reversed modifier by default', () => {
    const { container } = render(<FeatureRow content={makeContent('mint')} />);
    const article = container.querySelector('article.feature-row');
    expect(article?.classList.contains('feature-row--reversed')).toBe(false);
  });
});
