import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { TuesdayMirror } from './TuesdayMirror';

const YRDSB_FIXTURE = {
  board: 'YRDSB',
  display_name: 'York Region DSB',
  tools_named: ['Google Classroom', 'Teach Assist', 'Teams'],
  beats: [
    { index: 1, timestamp: '3:15 PM', without: 'Without 1', with: 'With 1' },
    { index: 2, timestamp: '3:42 PM', without: 'Without 2', with: 'With 2' },
    { index: 3, timestamp: '4:15 PM', without: 'Without 3', with: 'With 3' },
    { index: 4, timestamp: '5:30 PM', without: 'Without 4', with: 'With 4' },
    { index: 5, timestamp: '7:20 PM', without: 'Without 5', with: 'With 5' },
  ],
};

const TDSB_FIXTURE = { ...YRDSB_FIXTURE, board: 'TDSB', display_name: 'Toronto DSB' };

function mockMatchMedia(reduced: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn((query: string) => ({
      matches: query.includes('prefers-reduced-motion') && reduced,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    })),
  });
}

function mockFetch(responses: Record<string, unknown>) {
  global.fetch = vi.fn((url: string) => {
    const key = Object.keys(responses).find((k) => url.includes(k));
    if (!key) return Promise.reject(new Error(`Unexpected fetch: ${url}`));
    return Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve(responses[key]),
    } as Response);
  }) as unknown as typeof fetch;
}

describe('TuesdayMirror', () => {
  beforeEach(() => {
    window.localStorage.clear();
    mockMatchMedia(false);
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('renders all 5 beats synchronously in reduced-motion mode', async () => {
    mockMatchMedia(true);
    mockFetch({ 'yrdsb.json': YRDSB_FIXTURE });

    render(<TuesdayMirror />);

    await waitFor(() => {
      expect(screen.getByTestId('beat-without-5')).toHaveClass('tm-beat-visible');
    });
    for (let i = 1; i <= 5; i += 1) {
      expect(screen.getByTestId(`beat-without-${i}`)).toHaveClass('tm-beat-visible');
      expect(screen.getByTestId(`beat-with-${i}`)).toHaveClass('tm-beat-visible');
    }
  });

  it('reveals beats sequentially every 600ms in normal motion', async () => {
    mockMatchMedia(false);
    mockFetch({ 'yrdsb.json': YRDSB_FIXTURE });
    vi.useFakeTimers({ shouldAdvanceTime: true });

    render(<TuesdayMirror />);

    await waitFor(() => {
      expect(screen.getByTestId('beat-without-1')).toHaveClass('tm-beat-visible');
    });
    expect(screen.getByTestId('beat-without-2')).not.toHaveClass('tm-beat-visible');

    await act(async () => {
      await vi.advanceTimersByTimeAsync(600);
    });
    expect(screen.getByTestId('beat-without-2')).toHaveClass('tm-beat-visible');
    expect(screen.getByTestId('beat-without-3')).not.toHaveClass('tm-beat-visible');

    await act(async () => {
      await vi.advanceTimersByTimeAsync(600 * 3);
    });
    for (let i = 1; i <= 5; i += 1) {
      expect(screen.getByTestId(`beat-without-${i}`)).toHaveClass('tm-beat-visible');
    }
  });

  it('persists board selection to localStorage and restores it', async () => {
    mockMatchMedia(true);
    mockFetch({ 'yrdsb.json': YRDSB_FIXTURE, 'tdsb.json': TDSB_FIXTURE });

    const user = userEvent.setup();
    const { unmount } = render(<TuesdayMirror />);

    const select = await screen.findByLabelText('Select school board');
    await user.selectOptions(select, 'tdsb');
    expect(window.localStorage.getItem('classbridge_demo_board')).toBe('tdsb');

    unmount();
    render(<TuesdayMirror />);
    const select2 = await screen.findByLabelText('Select school board') as HTMLSelectElement;
    expect(select2.value).toBe('tdsb');
  });

  it('fetches the correct JSON when board changes', async () => {
    mockMatchMedia(true);
    mockFetch({ 'yrdsb.json': YRDSB_FIXTURE, 'tdsb.json': TDSB_FIXTURE });

    const user = userEvent.setup();
    render(<TuesdayMirror />);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/content/tuesday-mirror/yrdsb.json');
    });

    const select = screen.getByLabelText('Select school board');
    await user.selectOptions(select, 'tdsb');

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/content/tuesday-mirror/tdsb.json');
    });
  });

  it('CTA scrolls to #instant-trial section', async () => {
    mockMatchMedia(true);
    mockFetch({ 'yrdsb.json': YRDSB_FIXTURE });

    const trial = document.createElement('div');
    trial.id = 'instant-trial';
    const scrollSpy = vi.fn();
    trial.scrollIntoView = scrollSpy;
    document.body.appendChild(trial);

    const user = userEvent.setup();
    render(<TuesdayMirror />);

    const cta = await screen.findByRole('button', { name: /sounds familiar/i });
    await user.click(cta);

    expect(scrollSpy).toHaveBeenCalled();
    document.body.removeChild(trial);
  });

  it('applies aria-live="polite" to each beat container', async () => {
    mockMatchMedia(true);
    mockFetch({ 'yrdsb.json': YRDSB_FIXTURE });

    const { container } = render(<TuesdayMirror />);
    await waitFor(() => {
      expect(container.querySelectorAll('[aria-live="polite"]').length).toBe(2);
    });
  });

  it('mobile tab toggle switches visible column via data class', async () => {
    mockMatchMedia(true);
    mockFetch({ 'yrdsb.json': YRDSB_FIXTURE });

    const user = userEvent.setup();
    const { container } = render(<TuesdayMirror />);

    await waitFor(() => {
      expect(container.querySelector('.tm-grid')).not.toBeNull();
    });

    const grid = container.querySelector('.tm-grid') as HTMLElement;
    expect(grid.className).toContain('tm-mobile-without');

    const tabs = container.querySelectorAll('.tm-tab');
    const withoutTab = tabs[0] as HTMLButtonElement;
    const withTab = tabs[1] as HTMLButtonElement;
    expect(withoutTab.textContent).toMatch(/without/i);
    expect(withTab.textContent).toMatch(/^with/i);

    await user.click(withTab);
    expect(grid.className).toContain('tm-mobile-with');

    await user.click(withoutTab);
    expect(grid.className).toContain('tm-mobile-without');
  });
});
