import { fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../../test/helpers';
import RoleSwitcher from './RoleSwitcher';

const MOCK_DATA = {
  event: 'Franklin St. PS, Grade 8 ROM field trip, October 17',
  roles: {
    parent: {
      title: 'Parent view',
      content_items: [
        'Permission-slip deadline (sign and return).',
        '$22 fee — Interac tap-to-pay button.',
        'Dietary preferences confirmation.',
        'Bus pickup time.',
        'Emergency-contact confirmation.',
      ],
    },
    student: {
      title: 'Student view',
      content_items: [
        'Calendar entry: Thu Oct 17, 9:00 AM – 2:30 PM, Royal Ontario Museum.',
        'Packing checklist.',
        'Lunch option selector.',
        'Which friends have confirmed yes.',
      ],
    },
    teacher: {
      title: 'Teacher view',
      content_items: [
        'Roster: permission-status icons per student.',
        'Fee-collection dashboard.',
        'Bus seat assignment.',
        'Allergy alerts.',
        'One-tap reminder button.',
      ],
    },
    admin: {
      title: 'School Admin view',
      content_items: [
        'Approval status.',
        'Insurance documentation link.',
        'Total collected vs. owed.',
        'Opt-out count.',
        'MFIPPA compliance checklist.',
      ],
    },
  },
};

function mockFetchOk() {
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => MOCK_DATA,
  }) as unknown as typeof fetch;
}

function setReducedMotion(reduce: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn((query: string) => ({
      matches: reduce && query.includes('prefers-reduced-motion'),
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

describe('RoleSwitcher', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
    setReducedMotion(true); // default: skip fade for deterministic assertions
    mockFetchOk();
  });

  it('renders with Parent tab selected by default', async () => {
    renderWithProviders(<RoleSwitcher />);

    await waitFor(() => {
      expect(screen.getByText('Franklin St. PS, Grade 8 ROM field trip, October 17')).toBeInTheDocument();
    });

    const parentTab = screen.getByRole('tab', { name: /Parent view/i });
    expect(parentTab).toHaveAttribute('aria-selected', 'true');

    const studentTab = screen.getByRole('tab', { name: /Student view/i });
    expect(studentTab).toHaveAttribute('aria-selected', 'false');

    expect(screen.getByText('Permission-slip deadline (sign and return).')).toBeInTheDocument();
  });

  it('clicking a tab switches active tab and triggers fade transition', async () => {
    setReducedMotion(false); // enable motion so fade class applies

    renderWithProviders(<RoleSwitcher />);

    await waitFor(() => {
      expect(screen.getByText('Franklin St. PS, Grade 8 ROM field trip, October 17')).toBeInTheDocument();
    });

    const teacherTab = screen.getByRole('tab', { name: /Teacher view/i });

    // Synchronous click: fading class applies immediately, timeout resolves in 150ms
    fireEvent.click(teacherTab);

    const panelDuringFade = screen.getByRole('tabpanel');
    expect(panelDuringFade.className).toMatch(/role-switcher__panel--fading/);

    await waitFor(() => {
      expect(teacherTab).toHaveAttribute('aria-selected', 'true');
      expect(screen.getByText('Fee-collection dashboard.')).toBeInTheDocument();
    });
  });

  it('ArrowRight moves to next tab', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RoleSwitcher />);

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: /Parent view/i })).toBeInTheDocument();
    });

    const parentTab = screen.getByRole('tab', { name: /Parent view/i });
    parentTab.focus();
    await user.keyboard('{ArrowRight}');

    const studentTab = screen.getByRole('tab', { name: /Student view/i });
    expect(studentTab).toHaveAttribute('aria-selected', 'true');
    expect(studentTab).toHaveFocus();
  });

  it('ArrowLeft wraps from first to last', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RoleSwitcher />);

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: /Parent view/i })).toBeInTheDocument();
    });

    const parentTab = screen.getByRole('tab', { name: /Parent view/i });
    parentTab.focus();
    await user.keyboard('{ArrowLeft}');

    const adminTab = screen.getByRole('tab', { name: /School Admin view/i });
    expect(adminTab).toHaveAttribute('aria-selected', 'true');
    expect(adminTab).toHaveFocus();
  });

  it('Home jumps to first tab, End jumps to last', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RoleSwitcher />);

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: /Parent view/i })).toBeInTheDocument();
    });

    const parentTab = screen.getByRole('tab', { name: /Parent view/i });
    parentTab.focus();
    await user.keyboard('{End}');

    const adminTab = screen.getByRole('tab', { name: /School Admin view/i });
    expect(adminTab).toHaveAttribute('aria-selected', 'true');

    adminTab.focus();
    await user.keyboard('{Home}');
    expect(screen.getByRole('tab', { name: /Parent view/i })).toHaveAttribute('aria-selected', 'true');
  });

  it('tabpanel has aria-labelledby pointing to selected tab', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RoleSwitcher />);

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: /Parent view/i })).toBeInTheDocument();
    });

    const panel = screen.getByRole('tabpanel');
    expect(panel).toHaveAttribute('aria-labelledby', 'role-tab-parent');

    const teacherTab = screen.getByRole('tab', { name: /Teacher view/i });
    await user.click(teacherTab);

    await waitFor(() => {
      expect(screen.getByRole('tabpanel')).toHaveAttribute('aria-labelledby', 'role-tab-teacher');
    });
  });

  it('renders teacher "Fee-collection dashboard" and admin "MFIPPA compliance checklist"', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RoleSwitcher />);

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: /Teacher view/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('tab', { name: /Teacher view/i }));
    await waitFor(() => {
      expect(screen.getByText('Fee-collection dashboard.')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('tab', { name: /School Admin view/i }));
    await waitFor(() => {
      expect(screen.getByText('MFIPPA compliance checklist.')).toBeInTheDocument();
    });
  });

  it('prefers-reduced-motion disables fade (panel never gets fading class)', async () => {
    setReducedMotion(true);
    const user = userEvent.setup();

    renderWithProviders(<RoleSwitcher />);

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: /Parent view/i })).toBeInTheDocument();
    });

    const studentTab = screen.getByRole('tab', { name: /Student view/i });
    await user.click(studentTab);

    const panel = screen.getByRole('tabpanel');
    expect(panel.className).not.toMatch(/role-switcher__panel--fading/);
    expect(studentTab).toHaveAttribute('aria-selected', 'true');
  });

  it('CTA button dispatches demo:open-modal custom event when no prop handler passed', async () => {
    const user = userEvent.setup();
    const listener = vi.fn();
    window.addEventListener('demo:open-modal', listener);

    renderWithProviders(<RoleSwitcher />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /See this in my own school/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /See this in my own school/i }));

    expect(listener).toHaveBeenCalledTimes(1);
    window.removeEventListener('demo:open-modal', listener);
  });

  it('CTA calls onCtaClick prop when provided', async () => {
    const user = userEvent.setup();
    const onCta = vi.fn();

    renderWithProviders(<RoleSwitcher onCtaClick={onCta} />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /See this in my own school/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /See this in my own school/i }));
    expect(onCta).toHaveBeenCalledTimes(1);
  });
});
