import { describe, it, expect } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { LearnerSegmentTabs, section } from './LearnerSegmentTabs';
import { learnerSegments } from '../content/learnerSegments';

describe('LearnerSegmentTabs', () => {
  it('renders all 5 segment tabs from content', () => {
    render(<LearnerSegmentTabs />);
    const tabs = screen.getAllByRole('tab');
    expect(tabs).toHaveLength(5);
    expect(learnerSegments).toHaveLength(5);
    expect(tabs.map((t) => t.textContent)).toEqual(
      expect.arrayContaining(['Parents', 'Students', 'Teachers', 'Admins'].map(
        (name) => expect.stringContaining(name),
      )),
    );
  });

  it('wraps in <section data-landing="v2" class="landing-segments">', () => {
    const { container } = render(<LearnerSegmentTabs />);
    const wrapper = container.querySelector('section.landing-segments');
    expect(wrapper).not.toBeNull();
    expect(wrapper?.getAttribute('data-landing')).toBe('v2');
  });

  it('renders a vertical tablist with one tabpanel', () => {
    render(<LearnerSegmentTabs />);
    const tablist = screen.getByRole('tablist');
    expect(tablist.getAttribute('aria-orientation')).toBe('vertical');
    expect(screen.getAllByRole('tabpanel')).toHaveLength(1);
  });

  it('defaults to Parents tab active (cyan left-border modifier + aria-selected)', () => {
    render(<LearnerSegmentTabs />);
    const parentsTab = screen.getByRole('tab', { name: /Parents/i });
    expect(parentsTab.getAttribute('aria-selected')).toBe('true');
    expect(parentsTab.className).toContain('landing-segment-tab--active');
    const panel = screen.getByRole('tabpanel');
    expect(panel.getAttribute('aria-labelledby')).toBe(parentsTab.id);
  });

  it('shows the "Coming Phase 4" pill on the Private Tutors tab only', () => {
    render(<LearnerSegmentTabs />);
    const privateTutorsTab = screen.getByRole('tab', { name: /Private Tutors/i });
    expect(
      within(privateTutorsTab).getByText(/Coming Phase 4/i),
    ).toBeInTheDocument();

    // No other tab has a pill
    const otherTabs = screen
      .getAllByRole('tab')
      .filter((t) => t !== privateTutorsTab);
    otherTabs.forEach((tab) => {
      expect(within(tab).queryByText(/Coming Phase 4/i)).toBeNull();
    });
  });

  it('ArrowDown moves focus to the next tab and wraps from last to first', async () => {
    const user = userEvent.setup();
    render(<LearnerSegmentTabs />);
    const tabs = screen.getAllByRole('tab');

    tabs[0].focus();
    expect(document.activeElement).toBe(tabs[0]);

    await user.keyboard('{ArrowDown}');
    expect(document.activeElement).toBe(tabs[1]);

    // Wrap from the last tab back to the first
    tabs[tabs.length - 1].focus();
    await user.keyboard('{ArrowDown}');
    expect(document.activeElement).toBe(tabs[0]);
  });

  it('ArrowUp moves focus to the previous tab and wraps from first to last', async () => {
    const user = userEvent.setup();
    render(<LearnerSegmentTabs />);
    const tabs = screen.getAllByRole('tab');

    tabs[0].focus();
    await user.keyboard('{ArrowUp}');
    expect(document.activeElement).toBe(tabs[tabs.length - 1]);
  });

  it('Home/End jump to the first/last tab', async () => {
    const user = userEvent.setup();
    render(<LearnerSegmentTabs />);
    const tabs = screen.getAllByRole('tab');

    tabs[2].focus();
    await user.keyboard('{End}');
    expect(document.activeElement).toBe(tabs[tabs.length - 1]);

    await user.keyboard('{Home}');
    expect(document.activeElement).toBe(tabs[0]);
  });

  it('Enter activates the focused tab and updates the panel content', async () => {
    const user = userEvent.setup();
    render(<LearnerSegmentTabs />);

    const teachersTab = screen.getByRole('tab', { name: /Teachers/i });
    teachersTab.focus();
    await user.keyboard('{Enter}');

    expect(teachersTab.getAttribute('aria-selected')).toBe('true');
    const panel = screen.getByRole('tabpanel');
    expect(panel.getAttribute('aria-labelledby')).toBe(teachersTab.id);
    expect(within(panel).getByText(/Sync with Google Classroom/i)).toBeInTheDocument();
  });

  it('Space activates the focused tab', async () => {
    const user = userEvent.setup();
    render(<LearnerSegmentTabs />);

    const adminsTab = screen.getByRole('tab', { name: /Admins/i });
    adminsTab.focus();
    await user.keyboard(' ');

    expect(adminsTab.getAttribute('aria-selected')).toBe('true');
    const panel = screen.getByRole('tabpanel');
    expect(within(panel).getByText(/Platform health dashboard/i)).toBeInTheDocument();
    expect(within(panel).getByText(/Broadcast messaging/i)).toBeInTheDocument();
  });

  it('click activates a tab and swaps the panel bullets', async () => {
    const user = userEvent.setup();
    render(<LearnerSegmentTabs />);

    const studentsTab = screen.getByRole('tab', { name: /Students/i });
    await user.click(studentsTab);

    expect(studentsTab.getAttribute('aria-selected')).toBe('true');
    const panel = screen.getByRole('tabpanel');
    expect(within(panel).getByText(/AI study guides/i)).toBeInTheDocument();
    expect(within(panel).getByText(/Flash Tutor practice/i)).toBeInTheDocument();
  });

  it('active tab has tabIndex=0, inactive tabs have tabIndex=-1', () => {
    render(<LearnerSegmentTabs />);
    const tabs = screen.getAllByRole('tab');
    const active = tabs.find((t) => t.getAttribute('aria-selected') === 'true');
    expect(active?.getAttribute('tabindex')).toBe('0');
    tabs
      .filter((t) => t !== active)
      .forEach((t) => expect(t.getAttribute('tabindex')).toBe('-1'));
  });

  it('exports a glob-registry section descriptor', () => {
    expect(section.id).toBe('segments');
    expect(section.order).toBe(70);
    expect(section.component).toBe(LearnerSegmentTabs);
  });
});
