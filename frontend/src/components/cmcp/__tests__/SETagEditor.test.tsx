/**
 * CB-CMCP-001 M3-A 3A-3 (#4583) — SETagEditor unit tests.
 *
 * Coverage per acceptance criteria:
 * - Renders existing codes as chips.
 * - Remove chip → onChange called with the code removed.
 * - Type query → autocomplete renders suggestions (mock the search API).
 * - Select suggestion → onChange called with the code added.
 * - Disabled prop → no editing (no input, no remove buttons).
 * - Duplicate add is silently ignored.
 * - Free-text Enter adds the typed code verbatim when there is no match.
 *
 * The curriculum search API is mocked so no real network calls are made.
 * We use real timers + waitFor (not fake timers) because the combination
 * of vitest fake timers + userEvent typing has known timeout issues —
 * the debounce window is small (300ms) and the tests still finish quickly.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const mockSearchExpectations = vi.fn();

vi.mock('../../../api/curriculum', () => ({
  curriculumApi: {
    searchExpectations: (...args: unknown[]) =>
      mockSearchExpectations(...args),
  },
}));

import { SETagEditor } from '../SETagEditor';

const sampleResponse = {
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

describe('SETagEditor', () => {
  beforeEach(() => {
    mockSearchExpectations.mockReset();
  });

  it('renders existing codes as chips', () => {
    const onChange = vi.fn();
    render(
      <SETagEditor
        seCodes={['A1.1', 'B2.3']}
        onChange={onChange}
      />,
    );
    expect(screen.getByText('A1.1')).toBeInTheDocument();
    expect(screen.getByText('B2.3')).toBeInTheDocument();
    // Each chip has a remove button labelled with its code.
    expect(
      screen.getByRole('button', { name: 'Remove SE code A1.1' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Remove SE code B2.3' }),
    ).toBeInTheDocument();
  });

  it('shows the empty placeholder when there are no codes', () => {
    render(<SETagEditor seCodes={[]} onChange={vi.fn()} />);
    expect(screen.getByText('No SE codes attached.')).toBeInTheDocument();
  });

  it('removes a chip and calls onChange with the code removed', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <SETagEditor
        seCodes={['A1.1', 'B2.3']}
        onChange={onChange}
      />,
    );
    await user.click(
      screen.getByRole('button', { name: 'Remove SE code A1.1' }),
    );
    expect(onChange).toHaveBeenCalledWith(['B2.3']);
  });

  it('debounces input and renders autocomplete suggestions', async () => {
    const user = userEvent.setup();
    mockSearchExpectations.mockResolvedValue(sampleResponse);

    render(
      <SETagEditor
        seCodes={[]}
        onChange={vi.fn()}
        subjectCode="MATH"
        grade={7}
      />,
    );

    const input = screen.getByLabelText('Search and add SE code');
    await user.type(input, 'whole');

    // The debounce + axios round-trip should resolve quickly under
    // jsdom; waitFor handles the polling.
    await waitFor(() => {
      expect(mockSearchExpectations).toHaveBeenCalled();
    });
    // Last call uses the full typed query.
    expect(mockSearchExpectations).toHaveBeenLastCalledWith('MATH', 'whole');

    // Suggestions render — codes from sampleResponse are visible.
    await waitFor(() => {
      expect(screen.getByText('B1.1')).toBeInTheDocument();
    });
    expect(screen.getByText('B1.2')).toBeInTheDocument();
    expect(screen.getByText('C2.1')).toBeInTheDocument();
    // Strand label is shown alongside.
    expect(screen.getAllByText('Number').length).toBeGreaterThan(0);
  });

  it('does NOT call the search API when subjectCode is missing', async () => {
    const user = userEvent.setup();
    render(<SETagEditor seCodes={[]} onChange={vi.fn()} />);
    const input = screen.getByLabelText('Search and add SE code');
    await user.type(input, 'whole');
    // Wait long enough to be sure the debounce would have fired.
    await new Promise((r) => setTimeout(r, 500));
    expect(mockSearchExpectations).not.toHaveBeenCalled();
    expect(
      screen.getByText('Subject required to search curriculum.'),
    ).toBeInTheDocument();
  });

  it('selects a suggestion via mouse and calls onChange with the code added', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    mockSearchExpectations.mockResolvedValue(sampleResponse);

    render(
      <SETagEditor
        seCodes={['A1.1']}
        onChange={onChange}
        subjectCode="MATH"
      />,
    );
    const input = screen.getByLabelText('Search and add SE code');
    await user.type(input, 'whole');
    await waitFor(() => {
      expect(screen.getByText('B1.2')).toBeInTheDocument();
    });

    // Find the suggestion option containing 'B1.2'.
    const option = screen
      .getAllByRole('option')
      .find((el) => el.textContent?.includes('B1.2'));
    expect(option).toBeDefined();
    // The component uses onMouseDown to add — pointerDown via userEvent
    // triggers the same handler.
    await user.pointer({ keys: '[MouseLeft>]', target: option! });

    expect(onChange).toHaveBeenCalledWith(['A1.1', 'B1.2']);
  });

  it('adds a free-text code on Enter when no suggestion is active', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(
      <SETagEditor
        seCodes={['A1.1']}
        onChange={onChange}
      />,
    );
    const input = screen.getByLabelText('Search and add SE code');
    await user.type(input, 'Z9.9');
    await user.keyboard('{Enter}');
    expect(onChange).toHaveBeenCalledWith(['A1.1', 'Z9.9']);
  });

  it('silently ignores duplicate adds (case-insensitive)', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();

    render(
      <SETagEditor
        seCodes={['A1.1']}
        onChange={onChange}
      />,
    );
    const input = screen.getByLabelText('Search and add SE code');
    await user.type(input, 'a1.1');
    await user.keyboard('{Enter}');
    expect(onChange).not.toHaveBeenCalled();
  });

  it('disabled prop hides input and remove buttons', () => {
    render(
      <SETagEditor
        seCodes={['A1.1', 'B2.3']}
        onChange={vi.fn()}
        disabled
        subjectCode="MATH"
      />,
    );
    // Chips render as plain text — no remove buttons.
    expect(
      screen.queryByRole('button', { name: /Remove SE code/ }),
    ).not.toBeInTheDocument();
    // Input is hidden entirely.
    expect(
      screen.queryByLabelText('Search and add SE code'),
    ).not.toBeInTheDocument();
  });

  it('does NOT search on a single character (MIN_QUERY_LENGTH=2)', async () => {
    const user = userEvent.setup();
    mockSearchExpectations.mockResolvedValue(sampleResponse);

    render(
      <SETagEditor seCodes={[]} onChange={vi.fn()} subjectCode="MATH" />,
    );
    const input = screen.getByLabelText('Search and add SE code');
    await user.type(input, 'a');
    // Wait long enough that a debounced call would have fired.
    await new Promise((r) => setTimeout(r, 500));
    expect(mockSearchExpectations).not.toHaveBeenCalled();

    // Adding a second character triggers the search.
    await user.type(input, 'b');
    await waitFor(() => {
      expect(mockSearchExpectations).toHaveBeenCalledWith('MATH', 'ab');
    });
  });

  it('shows an error in the dropdown if the search request fails', async () => {
    const user = userEvent.setup();
    mockSearchExpectations.mockRejectedValue({
      response: { status: 500 },
    });

    render(
      <SETagEditor seCodes={[]} onChange={vi.fn()} subjectCode="MATH" />,
    );
    const input = screen.getByLabelText('Search and add SE code');
    await user.type(input, 'foo');
    await waitFor(() => {
      expect(
        screen.getByText('Could not load curriculum suggestions.'),
      ).toBeInTheDocument();
    });
  });
});
