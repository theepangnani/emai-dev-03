import { render, screen } from '@testing-library/react';
import { TaskSourceBadge } from '../TaskSourceBadge';

describe('TaskSourceBadge', () => {
  it('renders assignment badge with label and tooltip', () => {
    render(<TaskSourceBadge source="assignment" />);
    const badge = screen.getByRole('status');
    expect(badge).toHaveTextContent('Auto');
    expect(badge).toHaveAttribute('title', 'Auto-created from class assignment');
    expect(badge).toHaveClass('task-source-badge--assignment');
  });

  it('renders active email_digest badge', () => {
    render(<TaskSourceBadge source="email_digest" sourceStatus="active" />);
    const badge = screen.getByRole('status');
    expect(badge).toHaveTextContent('Auto');
    expect(badge).toHaveAttribute('title', 'Auto-created from teacher email');
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
    const badge = screen.getByRole('status');
    expect(badge).toHaveTextContent('Unverified');
    expect(badge).toHaveAttribute(
      'title',
      'Auto-created from teacher email (83% confidence) — please verify',
    );
    expect(badge).toHaveClass('task-source-badge--email-tentative');
  });

  it('renders tentative badge without percent when confidence missing', () => {
    render(<TaskSourceBadge source="email_digest" sourceStatus="tentative" />);
    const badge = screen.getByRole('status');
    expect(badge).toHaveAttribute(
      'title',
      'Auto-created from teacher email — please verify',
    );
  });

  it('renders study_guide neutral badge', () => {
    render(<TaskSourceBadge source="study_guide" />);
    const badge = screen.getByRole('status');
    expect(badge).toHaveTextContent('Auto (study guide)');
    expect(badge).toHaveClass('task-source-badge--study-guide');
  });

  it('renders nothing for source="manual"', () => {
    const { container } = render(<TaskSourceBadge source="manual" />);
    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('renders nothing for null source', () => {
    const { container } = render(<TaskSourceBadge source={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing for undefined source', () => {
    const { container } = render(<TaskSourceBadge />);
    expect(container).toBeEmptyDOMElement();
  });

  it('is keyboard-focusable for tooltip access', () => {
    render(<TaskSourceBadge source="assignment" />);
    const badge = screen.getByRole('status');
    expect(badge).toHaveAttribute('tabIndex', '0');
    badge.focus();
    expect(badge).toHaveFocus();
  });
});
