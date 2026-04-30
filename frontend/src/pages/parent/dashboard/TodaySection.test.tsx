/** CB-EDIGEST-002 Stripe E2 (#4590) — TodaySection tests. */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TodaySection, relativeDueLabel } from './TodaySection';
import type { KidSection, UrgentItem } from './TodaySection';

function makeItem(overrides: Partial<UrgentItem> = {}): UrgentItem {
  return {
    id: overrides.id ?? 'item-1',
    title: overrides.title ?? 'Math homework',
    due_date: overrides.due_date ?? null,
    course_or_context: overrides.course_or_context ?? 'Math 101',
    source_email_id: overrides.source_email_id ?? 'email-1',
  };
}

function makeKid(overrides: Partial<KidSection> = {}): KidSection {
  return {
    id: overrides.id ?? 1,
    first_name: overrides.first_name ?? 'Aanya',
    urgent_items: overrides.urgent_items ?? [],
    all_clear: overrides.all_clear ?? false,
  };
}

describe('TodaySection', () => {
  it('single kid with 2 urgent items renders both', () => {
    const items = [
      makeItem({ id: 'a', title: 'Math worksheet' }),
      makeItem({ id: 'b', title: 'Field trip form' }),
    ];
    const kid = makeKid({ urgent_items: items });

    render(<TodaySection kids={[kid]} onItemClick={vi.fn()} />);

    expect(screen.getByText('Math worksheet')).toBeInTheDocument();
    expect(screen.getByText('Field trip form')).toBeInTheDocument();
    expect(screen.getByText('Aanya')).toBeInTheDocument();
  });

  it('multi-kid: kid with 3 urgent first, kid with 0 urgent (all_clear) shows All clear panel', () => {
    const kid1 = makeKid({
      id: 1,
      first_name: 'Aanya',
      urgent_items: [
        makeItem({ id: 'a' }),
        makeItem({ id: 'b' }),
        makeItem({ id: 'c' }),
      ],
    });
    const kid2 = makeKid({
      id: 2,
      first_name: 'Rohan',
      urgent_items: [],
      all_clear: true,
    });

    render(<TodaySection kids={[kid2, kid1]} onItemClick={vi.fn()} />);

    const sections = screen.getAllByRole('article');
    // kid1 (3 urgent) renders before kid2 (0 urgent / all-clear).
    expect(within(sections[0]).getByText('Aanya')).toBeInTheDocument();
    expect(within(sections[1]).getByText('Rohan')).toBeInTheDocument();
    expect(screen.getByTestId('today-kid-2-all-clear')).toBeInTheDocument();
    expect(screen.getByText('All clear')).toBeInTheDocument();
  });

  it('multi-kid with same urgent count: ordered by id ASC', () => {
    const kidA = makeKid({
      id: 5,
      first_name: 'Eldest',
      urgent_items: [makeItem({ id: 'x' })],
    });
    const kidB = makeKid({
      id: 2,
      first_name: 'Middle',
      urgent_items: [makeItem({ id: 'y' })],
    });
    const kidC = makeKid({
      id: 9,
      first_name: 'Youngest',
      urgent_items: [makeItem({ id: 'z' })],
    });

    // Pass in unsorted order so sort logic actually runs.
    render(
      <TodaySection kids={[kidA, kidC, kidB]} onItemClick={vi.fn()} />,
    );

    const articles = screen.getAllByRole('article');
    expect(within(articles[0]).getByText('Middle')).toBeInTheDocument();
    expect(within(articles[1]).getByText('Eldest')).toBeInTheDocument();
    expect(within(articles[2]).getByText('Youngest')).toBeInTheDocument();
  });

  it('clicking an item fires onItemClick(kid_id, item)', async () => {
    const item = makeItem({ id: 'click-me', title: 'Permission slip' });
    const kid = makeKid({ id: 7, first_name: 'Liam', urgent_items: [item] });
    const handler = vi.fn();

    render(<TodaySection kids={[kid]} onItemClick={handler} />);

    const user = userEvent.setup();
    await user.click(screen.getByText('Permission slip'));

    expect(handler).toHaveBeenCalledTimes(1);
    expect(handler).toHaveBeenCalledWith(7, item);
  });

  it('with 4+ items: renders only first 3 + And N more CTA', () => {
    const items = [
      makeItem({ id: 'i1', title: 'Item 1' }),
      makeItem({ id: 'i2', title: 'Item 2' }),
      makeItem({ id: 'i3', title: 'Item 3' }),
      makeItem({ id: 'i4', title: 'Item 4' }),
      makeItem({ id: 'i5', title: 'Item 5' }),
    ];
    const kid = makeKid({ id: 3, urgent_items: items });

    render(<TodaySection kids={[kid]} onItemClick={vi.fn()} />);

    expect(screen.getByText('Item 1')).toBeInTheDocument();
    expect(screen.getByText('Item 2')).toBeInTheDocument();
    expect(screen.getByText('Item 3')).toBeInTheDocument();
    expect(screen.queryByText('Item 4')).not.toBeInTheDocument();
    expect(screen.queryByText('Item 5')).not.toBeInTheDocument();
    expect(screen.getByTestId('today-kid-3-more')).toHaveTextContent(
      /And 2 more/i,
    );
  });

  it('clicking "And N more" fires onItemClick(kid_id, null)', async () => {
    const items = [
      makeItem({ id: 'i1' }),
      makeItem({ id: 'i2' }),
      makeItem({ id: 'i3' }),
      makeItem({ id: 'i4' }),
    ];
    const kid = makeKid({ id: 11, urgent_items: items });
    const handler = vi.fn();

    render(<TodaySection kids={[kid]} onItemClick={handler} />);

    const user = userEvent.setup();
    await user.click(screen.getByTestId('today-kid-11-more'));

    expect(handler).toHaveBeenCalledTimes(1);
    expect(handler).toHaveBeenCalledWith(11, null);
  });

  it('renders relative due-date pill for items with due_date', () => {
    // Use a fixed "now" so the test is timezone- and date-stable.
    const now = new Date(2026, 4, 1, 12, 0, 0); // Fri, May 1 2026, noon local
    vi.useFakeTimers();
    vi.setSystemTime(now);

    const items = [
      makeItem({
        id: 'today',
        title: 'Today task',
        due_date: new Date(2026, 4, 1, 18, 0, 0).toISOString(),
      }),
      makeItem({
        id: 'tmrw',
        title: 'Tomorrow task',
        due_date: new Date(2026, 4, 2, 9, 0, 0).toISOString(),
      }),
    ];
    const kid = makeKid({ urgent_items: items });

    render(<TodaySection kids={[kid]} onItemClick={vi.fn()} />);

    expect(screen.getByText('Due today')).toBeInTheDocument();
    expect(screen.getByText('Due tomorrow')).toBeInTheDocument();

    vi.useRealTimers();
  });

  it('uses Bridge skin CSS variables (scoped under .bridge-page)', () => {
    const kid = makeKid({
      urgent_items: [makeItem({ id: 'css-check' })],
    });

    const { container } = render(
      <TodaySection kids={[kid]} onItemClick={vi.fn()} />,
    );

    // Root section is scoped under `.bridge-page` so all Bridge tokens
    // (--bridge-ink, --bridge-paper, --bridge-rust, etc.) cascade in.
    const root = container.querySelector('.bridge-page');
    expect(root).not.toBeNull();
    expect(root).toHaveClass('today-section');
    // Cards reuse the bridge-card primitive so they inherit Bridge tokens.
    expect(container.querySelector('.bridge-card')).not.toBeNull();
  });
});

describe('relativeDueLabel', () => {
  // Anchor "now" to a fixed local-midday weekday so weekday-name assertions
  // are deterministic regardless of test runner timezone.
  const now = new Date(2026, 4, 1, 12, 0, 0); // Fri, May 1 2026, noon

  it('returns null for null input', () => {
    expect(relativeDueLabel(null, now)).toBeNull();
  });

  it('returns null for unparseable input', () => {
    expect(relativeDueLabel('not-a-date', now)).toBeNull();
  });

  it('returns "Due today" for same calendar day', () => {
    const due = new Date(2026, 4, 1, 18, 0, 0).toISOString();
    expect(relativeDueLabel(due, now)).toBe('Due today');
  });

  it('returns "Due tomorrow" for next calendar day', () => {
    const due = new Date(2026, 4, 2, 9, 0, 0).toISOString();
    expect(relativeDueLabel(due, now)).toBe('Due tomorrow');
  });

  it('returns "Due {weekday}" for items 2-6 days out', () => {
    // May 4 2026 is a Monday.
    const due = new Date(2026, 4, 4, 9, 0, 0).toISOString();
    expect(relativeDueLabel(due, now)).toBe('Due Monday');
  });

  it('returns absolute "Due {Mon} {D}" for items >= 7 days out', () => {
    const due = new Date(2026, 4, 15, 9, 0, 0).toISOString();
    expect(relativeDueLabel(due, now)).toBe('Due May 15');
  });

  it('returns "Overdue" for past due dates', () => {
    const due = new Date(2026, 3, 30, 9, 0, 0).toISOString(); // Apr 30
    expect(relativeDueLabel(due, now)).toBe('Overdue');
  });
});
