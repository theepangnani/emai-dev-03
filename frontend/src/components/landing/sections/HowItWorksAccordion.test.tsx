import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HowItWorksAccordion, section } from './HowItWorksAccordion';
import { howItWorksSteps } from './howItWorks';

describe('HowItWorksAccordion', () => {
  it('renders all 4 steps', () => {
    render(<HowItWorksAccordion />);
    for (const step of howItWorksSteps) {
      expect(screen.getByText(step.title)).toBeInTheDocument();
    }
    expect(screen.getAllByRole('button')).toHaveLength(4);
  });

  it('marks the first step expanded by default', () => {
    render(<HowItWorksAccordion />);
    const rows = screen.getAllByRole('button');
    expect(rows[0]).toHaveAttribute('aria-expanded', 'true');
    expect(rows[1]).toHaveAttribute('aria-expanded', 'false');
    expect(rows[2]).toHaveAttribute('aria-expanded', 'false');
    expect(rows[3]).toHaveAttribute('aria-expanded', 'false');
  });

  it('activates a step on click', async () => {
    const user = userEvent.setup();
    render(<HowItWorksAccordion />);
    const rows = screen.getAllByRole('button');
    await user.click(rows[2]);
    expect(rows[0]).toHaveAttribute('aria-expanded', 'false');
    expect(rows[2]).toHaveAttribute('aria-expanded', 'true');
  });

  it('cycles through steps with ArrowDown / ArrowUp', async () => {
    const user = userEvent.setup();
    render(<HowItWorksAccordion />);
    const rows = screen.getAllByRole('button');
    rows[0].focus();
    await user.keyboard('{ArrowDown}');
    expect(rows[1]).toHaveAttribute('aria-expanded', 'true');
    await user.keyboard('{ArrowDown}');
    expect(rows[2]).toHaveAttribute('aria-expanded', 'true');
    await user.keyboard('{ArrowUp}');
    expect(rows[1]).toHaveAttribute('aria-expanded', 'true');
  });

  it('wraps focus with ArrowUp from the first step', async () => {
    const user = userEvent.setup();
    render(<HowItWorksAccordion />);
    const rows = screen.getAllByRole('button');
    rows[0].focus();
    await user.keyboard('{ArrowUp}');
    expect(rows[rows.length - 1]).toHaveAttribute('aria-expanded', 'true');
  });

  it('jumps to first/last with Home/End', async () => {
    const user = userEvent.setup();
    render(<HowItWorksAccordion />);
    const rows = screen.getAllByRole('button');
    rows[0].focus();
    await user.keyboard('{End}');
    expect(rows[3]).toHaveAttribute('aria-expanded', 'true');
    await user.keyboard('{Home}');
    expect(rows[0]).toHaveAttribute('aria-expanded', 'true');
  });

  it('exports a section registration object', () => {
    expect(section).toEqual({
      id: 'how',
      order: 40,
      component: HowItWorksAccordion,
    });
  });

  it('scopes the section under data-landing="v2"', () => {
    const { container } = render(<HowItWorksAccordion />);
    const sectionEl = container.querySelector('section.landing-how');
    expect(sectionEl).not.toBeNull();
    expect(sectionEl).toHaveAttribute('data-landing', 'v2');
  });
});
