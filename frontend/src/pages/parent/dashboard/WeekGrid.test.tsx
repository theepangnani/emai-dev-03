/** CB-EDIGEST-002 E3 (#4591) — WeekGrid tests. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { WeekGrid, type KidWeekRow, type DayBucket, type WeekDeadline } from './WeekGrid';

// ---- helpers ----

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] as const;

function makeItem(id: string, title: string): WeekDeadline {
  return {
    id,
    title,
    course_or_context: 'Math 101',
    source_email_id: `email-${id}`,
  };
}

function makeWeek(
  pastDays: number[],          // column indices considered past
  itemsByCol: Record<number, WeekDeadline[]>,
): DayBucket[] {
  return WEEKDAYS.map((wd, i) => ({
    day: `2026-04-${String(27 + i).padStart(2, '0')}`,
    weekday: wd,
    items: itemsByCol[i] ?? [],
    is_past: pastDays.includes(i),
  }));
}

function setMatchMedia(matches: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

beforeEach(() => {
  setMatchMedia(false); // default: desktop
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ---- tests ----

describe('WeekGrid — desktop layout', () => {
  it('renders a single-kid grid with 3 populated cells (Mon, Wed, Fri) and 4 empty cells', () => {
    const kids: KidWeekRow[] = [
      {
        id: 1,
        first_name: 'Aanya',
        days: makeWeek([], {
          0: [makeItem('a1', 'Math homework')],
          2: [makeItem('a2', 'Science quiz'), makeItem('a3', 'Reading')],
          4: [makeItem('a4', 'Spelling test')],
        }),
      },
    ];

    render(<WeekGrid kids={kids} onCellClick={() => {}} />);

    expect(screen.getByTestId('weekgrid-desktop')).toBeInTheDocument();
    expect(screen.getByText('Aanya')).toBeInTheDocument();

    // Count badges: there should be exactly 3 (one per populated day)
    const monCell = screen.getByTestId('weekgrid-cell-1-0');
    const tueCell = screen.getByTestId('weekgrid-cell-1-1');
    const wedCell = screen.getByTestId('weekgrid-cell-1-2');
    const friCell = screen.getByTestId('weekgrid-cell-1-4');

    expect(monCell.textContent).toContain('1');
    expect(monCell.textContent).toContain('Math homework');
    expect(wedCell.textContent).toContain('2');
    expect(wedCell.textContent).toContain('Science quiz');
    expect(friCell.textContent).toContain('1');
    expect(friCell.textContent).toContain('Spelling test');

    // Empty Tue cell: no count badge — assert via aria-label (0 items)
    expect(tueCell).toHaveAttribute('aria-label', expect.stringContaining('0 items'));
  });

  it('renders multi-kid rows in input order', () => {
    const kids: KidWeekRow[] = [
      { id: 11, first_name: 'Aanya', days: makeWeek([], { 0: [makeItem('x1', 'Task X')] }) },
      { id: 22, first_name: 'Brij', days: makeWeek([], { 1: [makeItem('y1', 'Task Y')] }) },
      { id: 33, first_name: 'Chitra', days: makeWeek([], { 2: [makeItem('z1', 'Task Z')] }) },
    ];

    render(<WeekGrid kids={kids} onCellClick={() => {}} />);

    const names = screen.getAllByRole('rowheader').map((el) => el.textContent);
    expect(names).toEqual(['Aanya', 'Brij', 'Chitra']);
  });

  it('greys out past-day cells (applies weekgrid-cell-past class) and strikes the count', () => {
    const kids: KidWeekRow[] = [
      {
        id: 1,
        first_name: 'Aanya',
        days: makeWeek([0, 1], {
          0: [makeItem('p1', 'Missed Mon')],
          2: [makeItem('p2', 'Today Wed')],
        }),
      },
    ];

    render(<WeekGrid kids={kids} onCellClick={() => {}} />);

    const monCell = screen.getByTestId('weekgrid-cell-1-0');
    const tueCell = screen.getByTestId('weekgrid-cell-1-1');
    const wedCell = screen.getByTestId('weekgrid-cell-1-2');

    expect(monCell.className).toContain('weekgrid-cell-past');
    expect(tueCell.className).toContain('weekgrid-cell-past');
    expect(wedCell.className).not.toContain('weekgrid-cell-past');

    // Past-day count carries the strike modifier class
    const monCount = monCell.querySelector('.weekgrid-cell-count');
    expect(monCount?.className).toContain('weekgrid-cell-count-past');
  });

  it('fires onCellClick with correct (kid_id, day) when a cell is clicked', () => {
    const onCellClick = vi.fn();
    const kids: KidWeekRow[] = [
      {
        id: 42,
        first_name: 'Aanya',
        days: makeWeek([], { 2: [makeItem('c1', 'Click me')] }),
      },
    ];

    render(<WeekGrid kids={kids} onCellClick={onCellClick} />);

    const wedCell = screen.getByTestId('weekgrid-cell-42-2');
    fireEvent.click(wedCell);

    expect(onCellClick).toHaveBeenCalledTimes(1);
    expect(onCellClick).toHaveBeenCalledWith(42, kids[0].days[2]);
  });

  it('renders the empty-state hint when no kid has any items this week', () => {
    const kids: KidWeekRow[] = [
      { id: 1, first_name: 'Aanya', days: makeWeek([], {}) },
      { id: 2, first_name: 'Brij', days: makeWeek([], {}) },
    ];

    render(<WeekGrid kids={kids} onCellClick={() => {}} />);

    expect(screen.getByTestId('weekgrid-empty')).toBeInTheDocument();
    expect(screen.getByText(/no deadlines this week/i)).toBeInTheDocument();
    expect(screen.queryByTestId('weekgrid-desktop')).not.toBeInTheDocument();
    expect(screen.queryByTestId('weekgrid-mobile')).not.toBeInTheDocument();
  });
});

describe('WeekGrid — mobile layout', () => {
  beforeEach(() => {
    setMatchMedia(true); // mobile
  });

  it('switches to vertical day-list rendering at < 768px and hides empty days', () => {
    const kids: KidWeekRow[] = [
      {
        id: 1,
        first_name: 'Aanya',
        days: makeWeek([], {
          0: [makeItem('m1', 'Mon item')],
          4: [makeItem('m2', 'Fri item')],
        }),
      },
    ];

    render(<WeekGrid kids={kids} onCellClick={() => {}} />);

    expect(screen.getByTestId('weekgrid-mobile')).toBeInTheDocument();
    expect(screen.queryByTestId('weekgrid-desktop')).not.toBeInTheDocument();

    // Only Mon and Fri sections appear (empty days hidden).
    const headings = screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent);
    expect(headings).toEqual(['Mon', 'Fri']);

    expect(screen.getByText('Mon item')).toBeInTheDocument();
    expect(screen.getByText('Fri item')).toBeInTheDocument();
  });
});
