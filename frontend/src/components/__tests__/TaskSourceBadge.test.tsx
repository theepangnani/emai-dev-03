import { render, screen } from '@testing-library/react';
import { TaskSourceBadge } from '../TaskSourceBadge';

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
});
