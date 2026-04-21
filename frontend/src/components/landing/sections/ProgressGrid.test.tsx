import { render, screen, within } from '@testing-library/react';

import { ProgressGrid, section } from './ProgressGrid';

describe('ProgressGrid (CB-LAND-001 S8)', () => {
  it('renders the serif-italic headline accent', () => {
    render(<ProgressGrid />);
    const heading = screen.getByRole('heading', { level: 2 });
    expect(heading).toHaveTextContent(/Progress for\s+every child, every week\./);
    const em = heading.querySelector('em');
    expect(em).not.toBeNull();
    expect(em).toHaveTextContent('every child, every week.');
  });

  it('renders all 4 feature cards with titles and bodies', () => {
    render(<ProgressGrid />);
    const list = screen.getByRole('list');
    const items = within(list).getAllByRole('listitem');
    expect(items).toHaveLength(4);

    expect(screen.getByText('Real-Time Activity Feed')).toBeInTheDocument();
    expect(
      screen.getByText('See every upload, quiz, and message as it happens.'),
    ).toBeInTheDocument();

    expect(screen.getByText('Streak / XP')).toBeInTheDocument();
    expect(
      screen.getByText('Celebrate consistency with Flash Tutor streaks and badges.'),
    ).toBeInTheDocument();

    expect(screen.getByText('Per-Child Focus Panel')).toBeInTheDocument();
    expect(
      screen.getByText(
        'Each child has their own week-at-a-glance — overdue, due today, coming up.',
      ),
    ).toBeInTheDocument();

    expect(screen.getByText('Resume Where You Left Off')).toBeInTheDocument();
    expect(
      screen.getByText(
        'Pick up Flash Tutor, quizzes, and study guides from anywhere.',
      ),
    ).toBeInTheDocument();
  });

  it('scopes the section under data-landing="v2" with the landing-progress class', () => {
    const { container } = render(<ProgressGrid />);
    const sectionEl = container.querySelector('section.landing-progress');
    expect(sectionEl).not.toBeNull();
    expect(sectionEl).toHaveAttribute('data-landing', 'v2');
  });

  it('exports a section registry entry with id "progress" and order 60', () => {
    expect(section).toMatchObject({
      id: 'progress',
      order: 60,
      component: ProgressGrid,
    });
  });
});
