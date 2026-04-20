import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { InstantTrialModal } from './InstantTrialModal';

/**
 * Regression test for #3761: the demo modal body's scrollbar track was being
 * clipped by the modal's rounded corners. Fix uses scrollbar-gutter: stable
 * plus extra right padding so the track sits inside the rounded rectangle.
 *
 * jsdom does not render scrollbars, so we assert on the DOM / stylesheet
 * state that guarantees the fix rather than on pixel geometry.
 */
describe('InstantTrialModal — scrollbar not clipped by rounded corners (#3761)', () => {
  it('renders .demo-modal-body inside the rounded .demo-modal container', () => {
    const { container } = render(<InstantTrialModal onClose={() => {}} />);
    const modal = container.querySelector('.demo-modal');
    const body = container.querySelector('.demo-modal-body');
    expect(modal).not.toBeNull();
    expect(body).not.toBeNull();
    expect(modal?.contains(body!)).toBe(true);
  });

  it('demo-modal-body CSS rule reserves a scrollbar gutter or extra right padding', () => {
    // Load the CSS text so we can assert the style rule matches the fix,
    // independent of jsdom's spotty getComputedStyle support for custom
    // properties and scrollbar-gutter.
    // The actual CSS file is imported by the component, so it lives in one of
    // the document's stylesheets.
    render(<InstantTrialModal onClose={() => {}} />);

    const sheets = Array.from(document.styleSheets) as CSSStyleSheet[];
    let foundRule: CSSStyleRule | undefined;
    for (const sheet of sheets) {
      let rules: CSSRuleList;
      try {
        rules = sheet.cssRules;
      } catch {
        continue;
      }
      for (const rule of Array.from(rules)) {
        if (
          rule instanceof CSSStyleRule &&
          rule.selectorText === '.demo-modal-body'
        ) {
          foundRule = rule;
          break;
        }
      }
      if (foundRule) break;
    }

    // In the vitest/jsdom setup the CSS is imported via Vite and may be
    // injected either as a CSSRule or as raw text. Fall back to scanning
    // <style> element text content if the rule object wasn't found.
    if (!foundRule) {
      const styleText = Array.from(document.querySelectorAll('style'))
        .map((s) => s.textContent || '')
        .join('\n');
      // Either the stable gutter OR the widened right padding proves the fix.
      const hasGutter = /\.demo-modal-body\s*\{[^}]*scrollbar-gutter\s*:\s*stable/s.test(
        styleText,
      );
      const hasWidenedPadding =
        /\.demo-modal-body\s*\{[^}]*padding\s*:[^;}]*var\(--space-xl\)/s.test(styleText);
      expect(hasGutter || hasWidenedPadding).toBe(true);
      return;
    }

    const gutter = foundRule.style.getPropertyValue('scrollbar-gutter').trim();
    const paddingRight = foundRule.style.getPropertyValue('padding-right').trim();
    const paddingShorthand = foundRule.style.getPropertyValue('padding').trim();
    // The fix sets scrollbar-gutter: stable AND bumps the right padding via
    // the padding shorthand. Either is sufficient evidence of the regression
    // fix, but we expect at least one.
    const hasGutter = gutter === 'stable' || gutter.startsWith('stable');
    const hasPaddingFix =
      paddingRight.length > 0 ||
      /var\(--space-xl\)/.test(paddingShorthand);
    expect(hasGutter || hasPaddingFix).toBe(true);
  });
});
