/**
 * CB-CMCP-001 M3-F 3F-1 (#4656) — CurriculumBrowser unit tests.
 *
 * Coverage per acceptance criteria:
 * - Tree renders from mocked CEG data (subject → strand → expectation).
 * - Multi-pick adds chips and onSelectionChange fires with the running list.
 * - Removing a chip removes the code from selection.
 * - Selection persists when navigating between subjects.
 * - View toggle (tree ↔ table) renders the same data in both shapes.
 * - Initial selection is honored.
 * - Grade filter excludes lower-grade subjects.
 * - The API client is mocked — no real network calls fire.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const mockListCourses = vi.fn();
const mockGetCourse = vi.fn();

vi.mock('../../../api/curriculumBrowser', () => ({
  curriculumBrowserApi: {
    listCourses: (...args: unknown[]) => mockListCourses(...args),
    getCourse: (...args: unknown[]) => mockGetCourse(...args),
  },
}));

import { CurriculumBrowser } from '../CurriculumBrowser';

const courseList = [
  { course_code: 'MATH', grade_level: 7, expectation_count: 12 },
  { course_code: 'LANG', grade_level: 5, expectation_count: 8 },
];

const mathCourse = {
  course_code: 'MATH',
  grade_level: 7,
  strands: [
    {
      name: 'Number',
      expectations: [
        {
          code: 'B1.1',
          description: 'Read and represent whole numbers up to 1 000 000.',
          type: 'specific',
        },
        {
          code: 'B1.2',
          description: 'Compare and order whole numbers up to 1 000 000.',
          type: 'specific',
        },
      ],
    },
    {
      name: 'Algebra',
      expectations: [
        {
          code: 'C2.1',
          description: 'Identify and use repeating patterns in algebra.',
          type: 'specific',
        },
      ],
    },
  ],
};

const langCourse = {
  course_code: 'LANG',
  grade_level: 5,
  strands: [
    {
      name: 'Reading',
      expectations: [
        {
          code: 'A1.1',
          description: 'Read a variety of texts.',
          type: 'specific',
        },
      ],
    },
  ],
};

describe('CurriculumBrowser', () => {
  beforeEach(() => {
    mockListCourses.mockReset();
    mockGetCourse.mockReset();
  });

  it('renders subjects column from listCourses() and tree from getCourse()', async () => {
    mockListCourses.mockResolvedValue(courseList);
    mockGetCourse.mockImplementation((code: string) =>
      Promise.resolve(code === 'MATH' ? mathCourse : langCourse),
    );

    render(<CurriculumBrowser onSelectionChange={vi.fn()} />);

    // Subjects load.
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /MATH/ })).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /LANG/ })).toBeInTheDocument();

    // Detail loads for the auto-picked first subject (MATH).
    await waitFor(() => {
      expect(mockGetCourse).toHaveBeenCalledWith('MATH');
    });

    // Tree renders strands + expectations.
    await waitFor(() => {
      expect(screen.getByText('Number')).toBeInTheDocument();
    });
    expect(screen.getByText('Algebra')).toBeInTheDocument();
    expect(screen.getByText('B1.1')).toBeInTheDocument();
    expect(screen.getByText('B1.2')).toBeInTheDocument();
    expect(screen.getByText('C2.1')).toBeInTheDocument();
  });

  it('multi-picks expectations and emits onSelectionChange with the running list', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    mockListCourses.mockResolvedValue(courseList);
    mockGetCourse.mockResolvedValue(mathCourse);

    render(<CurriculumBrowser onSelectionChange={onChange} />);

    await waitFor(() => {
      expect(screen.getByText('B1.1')).toBeInTheDocument();
    });

    // Pick two expectations via their checkboxes.
    await user.click(
      screen.getByRole('checkbox', { name: 'Select expectation B1.1' }),
    );
    await user.click(
      screen.getByRole('checkbox', { name: 'Select expectation C2.1' }),
    );

    expect(onChange).toHaveBeenNthCalledWith(1, ['B1.1']);
    expect(onChange).toHaveBeenNthCalledWith(2, ['B1.1', 'C2.1']);

    // Both chips render in the selected area.
    const chipList = screen.getByRole('list', {
      name: /selected expectations/i,
    });
    // Defensive in case role-by-name matching is brittle: also assert chip
    // text content.
    expect(within(chipList).getByText('B1.1')).toBeInTheDocument();
    expect(within(chipList).getByText('C2.1')).toBeInTheDocument();
  });

  it('removing a chip drops the code from selection and fires onSelectionChange', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    mockListCourses.mockResolvedValue(courseList);
    mockGetCourse.mockResolvedValue(mathCourse);

    render(
      <CurriculumBrowser
        onSelectionChange={onChange}
        initialSelection={['B1.1', 'C2.1']}
      />,
    );

    // Wait until the heading reflects the seeded selection so we know the
    // initial render has settled.
    await waitFor(() => {
      expect(screen.getByText('Selected (2)')).toBeInTheDocument();
    });

    await user.click(
      screen.getByRole('button', { name: 'Remove SE code B1.1' }),
    );

    expect(onChange).toHaveBeenLastCalledWith(['C2.1']);
    expect(screen.getByText('Selected (1)')).toBeInTheDocument();
  });

  it('persists selection when navigating between subjects', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    mockListCourses.mockResolvedValue(courseList);
    mockGetCourse.mockImplementation((code: string) =>
      Promise.resolve(code === 'MATH' ? mathCourse : langCourse),
    );

    render(<CurriculumBrowser onSelectionChange={onChange} />);

    await waitFor(() => {
      expect(screen.getByText('B1.1')).toBeInTheDocument();
    });

    // Pick MATH B1.1.
    await user.click(
      screen.getByRole('checkbox', { name: 'Select expectation B1.1' }),
    );
    expect(onChange).toHaveBeenLastCalledWith(['B1.1']);

    // Switch to LANG.
    await user.click(screen.getByRole('button', { name: /LANG/ }));
    await waitFor(() => {
      expect(screen.getByText('Reading')).toBeInTheDocument();
    });

    // Pick LANG A1.1.
    await user.click(
      screen.getByRole('checkbox', { name: 'Select expectation A1.1' }),
    );
    expect(onChange).toHaveBeenLastCalledWith(['B1.1', 'A1.1']);

    // Both chips persist after the subject swap.
    expect(screen.getByText('Selected (2)')).toBeInTheDocument();
    const chipList = screen.getByRole('list', {
      name: /selected expectations/i,
    });
    expect(within(chipList).getByText('B1.1')).toBeInTheDocument();
    expect(within(chipList).getByText('A1.1')).toBeInTheDocument();

    // Switch back to MATH — the previously-picked B1.1 checkbox should
    // still be checked because selection state is owned by the browser.
    await user.click(screen.getByRole('button', { name: /MATH/ }));
    await waitFor(() => {
      expect(
        screen.getByRole('checkbox', { name: 'Select expectation B1.1' }),
      ).toBeInTheDocument();
    });
    const b11Checkbox = screen.getByRole('checkbox', {
      name: 'Select expectation B1.1',
    });
    expect(b11Checkbox).toBeChecked();
  });

  it('toggles between tree and table view', async () => {
    const user = userEvent.setup();
    mockListCourses.mockResolvedValue(courseList);
    mockGetCourse.mockResolvedValue(mathCourse);

    render(<CurriculumBrowser onSelectionChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('B1.1')).toBeInTheDocument();
    });

    // Tree view is default. No table is rendered.
    expect(screen.queryByRole('table')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Table' }));

    // Table view: a <table> appears with rows for every expectation.
    const table = screen.getByRole('table');
    expect(table).toBeInTheDocument();
    expect(within(table).getByText('B1.1')).toBeInTheDocument();
    expect(within(table).getByText('B1.2')).toBeInTheDocument();
    expect(within(table).getByText('C2.1')).toBeInTheDocument();
  });

  it('honors initialSelection on mount', async () => {
    mockListCourses.mockResolvedValue(courseList);
    mockGetCourse.mockResolvedValue(mathCourse);

    render(
      <CurriculumBrowser
        onSelectionChange={vi.fn()}
        initialSelection={['B1.1', 'X9.9']}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText('Selected (2)')).toBeInTheDocument();
    });
    const chipList = screen.getByRole('list', {
      name: /selected expectations/i,
    });
    expect(within(chipList).getByText('B1.1')).toBeInTheDocument();
    // Even codes that aren't visible in the active subject's tree still
    // render as chips — the chip area is the running selection.
    expect(within(chipList).getByText('X9.9')).toBeInTheDocument();
  });

  it('filters subjects by the grade prop (lower bound on grade_level)', async () => {
    mockListCourses.mockResolvedValue(courseList);
    mockGetCourse.mockResolvedValue(mathCourse);

    render(<CurriculumBrowser onSelectionChange={vi.fn()} grade={6} />);

    // MATH (grade_level 7) is in. LANG (grade_level 5) is out.
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /MATH/ })).toBeInTheDocument();
    });
    expect(
      screen.queryByRole('button', { name: /LANG/ }),
    ).not.toBeInTheDocument();
  });

  it('shows an error in the subjects column when listCourses fails', async () => {
    mockListCourses.mockRejectedValue(new Error('boom'));

    render(<CurriculumBrowser onSelectionChange={vi.fn()} />);

    await waitFor(() => {
      expect(
        screen.getByText('Could not load curriculum subjects.'),
      ).toBeInTheDocument();
    });
  });
});
