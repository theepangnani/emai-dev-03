import { render, screen } from '@testing-library/react';
import { TaskSourceBadge } from '../TaskSourceBadge';
// I9 (#3921) — the badge's styles live in TasksPage.css (scoped alongside
// task-row styling). Import here so `getComputedStyle` and CSSStyleSheet
// walks see the transition + :focus-visible rules in tests.
import '../../pages/TasksPage.css';

describe('TaskSourceBadge', () => {
  it('renders assignment badge with label and tooltip', () => {
    render(<TaskSourceBadge source="assignment" />);
    const badge = screen.getByLabelText('Auto-created from class assignment');
    expect(badge).toHaveTextContent('Auto');
    expect(badge).toHaveAttribute('title', 'Auto-created from class assignment');
    expect(badge).toHaveClass('task-source-badge--assignment');
  });

  it('renders active email_digest badge', () => {
    render(<TaskSourceBadge source="email_digest" sourceStatus="active" />);
    const badge = screen.getByLabelText('Auto-created from teacher email');
    expect(badge).toHaveTextContent('Auto');
    expect(badge).toHaveClass('task-source-badge--email-active');
  });

  it('renders tentative email_digest badge with confidence percent', () => {
    render(
      <TaskSourceBadge
        source="email_digest"
        sourceStatus="tentative"
        confidence={0.826}
      />,
    );
    const badge = screen.getByLabelText(
      'Auto-created from teacher email (83% confidence) — please verify',
    );
    expect(badge).toHaveTextContent('Unverified');
    expect(badge).toHaveAttribute(
      'title',
      'Auto-created from teacher email (83% confidence) — please verify',
    );
    expect(badge).toHaveClass('task-source-badge--email-tentative');
  });

  it('renders tentative badge without percent when confidence missing', () => {
    render(<TaskSourceBadge source="email_digest" sourceStatus="tentative" />);
    const badge = screen.getByLabelText(
      'Auto-created from teacher email — please verify',
    );
    expect(badge).toBeInTheDocument();
  });

  it('renders study_guide neutral badge', () => {
    render(<TaskSourceBadge source="study_guide" />);
    const badge = screen.getByLabelText('Auto-created from a study guide');
    expect(badge).toHaveTextContent('Auto (study guide)');
    expect(badge).toHaveClass('task-source-badge--study-guide');
  });

  it('renders nothing for source="manual"', () => {
    const { container } = render(<TaskSourceBadge source="manual" />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing for null source', () => {
    const { container } = render(<TaskSourceBadge source={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing for undefined source', () => {
    const { container } = render(<TaskSourceBadge />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders neutral fallback for unknown non-null source values', () => {
    // Forward-compatibility: a new backend value shouldn't render invisibly.
    render(<TaskSourceBadge source={'whatsapp_digest' as never} />);
    const badge = screen.getByLabelText('Auto-created');
    expect(badge).toHaveTextContent('Auto');
    expect(badge).toHaveClass('task-source-badge--unknown');
  });

  it('does not add a keyboard tab-stop (non-interactive row decoration)', () => {
    render(<TaskSourceBadge source="assignment" />);
    const badge = screen.getByLabelText('Auto-created from class assignment');
    expect(badge).not.toHaveAttribute('tabIndex');
  });

  it('does not expose a live region (no role="status")', () => {
    render(<TaskSourceBadge source="assignment" />);
    expect(screen.queryByRole('status')).toBeNull();
  });

  // ------------------------------------------------------------------
  // I9 polish (#3921) — tooltip dates, inline confidence, transition/focus
  // ------------------------------------------------------------------

  it('tentative shows confidence percent inline in the label', () => {
    render(
      <TaskSourceBadge
        source="email_digest"
        sourceStatus="tentative"
        confidence={0.72}
      />,
    );
    // Label renders "Unverified · 72%" so low-confidence items are visible
    // without hovering for the tooltip.
    const badge = screen.getByTitle(
      'Auto-created from teacher email (72% confidence) — please verify',
    );
    expect(badge.textContent).toMatch(/Unverified\s*·\s*72%/);
  });

  it('active email_digest tooltip includes the formatted source-created date', () => {
    render(
      <TaskSourceBadge
        source="email_digest"
        sourceStatus="active"
        sourceCreatedAt="2026-04-21T12:00:00Z"
      />,
    );
    // "MMM d" → "Apr 21" from Intl.DateTimeFormat en-US.
    const badge = screen.getByLabelText(
      'Auto-created from teacher email on Apr 21',
    );
    expect(badge).toHaveAttribute(
      'title',
      'Auto-created from teacher email on Apr 21',
    );
  });

  it('tentative tooltip combines date and confidence percent', () => {
    render(
      <TaskSourceBadge
        source="email_digest"
        sourceStatus="tentative"
        confidence={0.72}
        sourceCreatedAt="2026-04-21T12:00:00Z"
      />,
    );
    const badge = screen.getByLabelText(
      'Auto-created from teacher email on Apr 21 (72% confidence) — please verify',
    );
    expect(badge).toBeInTheDocument();
  });

  it('assignment tooltip includes source-created date when provided', () => {
    render(
      <TaskSourceBadge
        source="assignment"
        sourceCreatedAt="2026-04-21T12:00:00Z"
      />,
    );
    const badge = screen.getByLabelText(
      'Auto-created from class assignment on Apr 21',
    );
    expect(badge).toBeInTheDocument();
  });

  it('falls back to legacy tooltip copy when source_created_at is missing', () => {
    render(<TaskSourceBadge source="assignment" />);
    const badge = screen.getByLabelText('Auto-created from class assignment');
    expect(badge).toBeInTheDocument();
  });

  it('falls back to legacy tooltip copy when source_created_at is invalid', () => {
    render(
      <TaskSourceBadge source="assignment" sourceCreatedAt="not-a-date" />,
    );
    const badge = screen.getByLabelText('Auto-created from class assignment');
    expect(badge).toBeInTheDocument();
  });

  it('applies a CSS transition on background/border so variant flips fade softly', () => {
    // jsdom does not cascade stylesheet rules into `getComputedStyle`, so we
    // assert the declared rule instead. This guards against accidental
    // removal of the I9 fade between variants (e.g. email_digest →
    // assignment upgrade from I6).
    const rules = Array.from(document.styleSheets).flatMap((sheet) => {
      try {
        return Array.from(sheet.cssRules ?? []);
      } catch {
        return [];
      }
    });
    const baseRule = rules.find(
      (r): r is CSSStyleRule =>
        r instanceof CSSStyleRule &&
        r.selectorText === '.task-source-badge',
    );
    expect(baseRule).toBeDefined();
    const transition = baseRule?.style.transition ?? '';
    expect(transition).toMatch(/background-color/);
    expect(transition).toMatch(/border-color/);
    expect(transition).toMatch(/300ms/);
  });

  it('declares a scoped :focus-visible outline rule in CSS', () => {
    // The badge is non-interactive today (no tabIndex per I8), but we still
    // ship a scoped :focus-visible rule so future wrappers (or tabIndex
    // additions) render a consistent ring. We assert the rule exists rather
    // than synthesizing focus in jsdom (which does not resolve
    // :focus-visible reliably).
    const rules = Array.from(document.styleSheets).flatMap((sheet) => {
      try {
        return Array.from(sheet.cssRules ?? []);
      } catch {
        return [];
      }
    });
    const focusRule = rules.find(
      (r): r is CSSStyleRule =>
        r instanceof CSSStyleRule &&
        r.selectorText === '.task-source-badge:focus-visible',
    );
    expect(focusRule).toBeDefined();
    expect(focusRule?.style.outline || focusRule?.style.getPropertyValue('outline')).toMatch(/2px/);
  });
});
