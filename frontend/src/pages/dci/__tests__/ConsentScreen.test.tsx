// CB-DCI-001 M0-11 — ConsentScreen tests (#4148)
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

import { renderWithProviders } from '../../../test/helpers';

const mockKids = [
  {
    student_id: 11,
    user_id: 110,
    full_name: 'Haashini',
    email: null,
    grade_level: 5,
    school_name: null,
    date_of_birth: null,
    phone: null,
    address: null,
    city: null,
    province: null,
    postal_code: null,
    notes: null,
    interests: [],
    relationship_type: 'mother',
    invite_link: null,
    course_count: 0,
    active_task_count: 0,
    invite_status: 'active' as const,
    invite_id: null,
  },
  {
    student_id: 12,
    user_id: 111,
    full_name: 'Arjun',
    email: null,
    grade_level: 8,
    school_name: null,
    date_of_birth: null,
    phone: null,
    address: null,
    city: null,
    province: null,
    postal_code: null,
    notes: null,
    interests: [],
    relationship_type: 'mother',
    invite_link: null,
    course_count: 0,
    active_task_count: 0,
    invite_status: 'active' as const,
    invite_id: null,
  },
];

const mockGetChildren = vi.fn().mockResolvedValue(mockKids);
const mockGet = vi.fn();
const mockUpsert = vi.fn();

vi.mock('../../../api/parent', () => ({
  parentApi: {
    getChildren: () => mockGetChildren(),
  },
}));

vi.mock('../../../api/dciConsent', () => ({
  dciConsentApi: {
    list: vi.fn(),
    get: (kidId: number) => mockGet(kidId),
    upsert: (update: unknown) => mockUpsert(update),
  },
}));

import { ConsentScreen } from '../ConsentScreen';

function defaultConsent(kidId: number) {
  return {
    parent_id: 1,
    kid_id: kidId,
    photo_ok: false,
    voice_ok: false,
    ai_ok: false,
    retention_days: 90,
    dci_enabled: true,
    muted: false,
    kid_push_time: '15:15',
    parent_push_time: '19:00',
    allowed_retention_days: [90, 365, 1095],
  };
}

beforeEach(() => {
  mockGetChildren.mockClear();
  mockGet.mockReset();
  mockUpsert.mockReset();
  mockGet.mockImplementation((kidId: number) =>
    Promise.resolve(defaultConsent(kidId)),
  );
  mockUpsert.mockImplementation((update: { kid_id: number } & Record<string, unknown>) =>
    Promise.resolve({ ...defaultConsent(update.kid_id), ...update }),
  );
});

describe('ConsentScreen', () => {
  it('renders Bill 194 disclosure', async () => {
    renderWithProviders(<ConsentScreen />);
    expect(await screen.findByTestId('bill-194-disclosure')).toBeInTheDocument();
    expect(
      screen.getByText(/AI will read this to help your parents/i),
    ).toBeInTheDocument();
  });

  it('renders all consent toggles + retention picker', async () => {
    renderWithProviders(<ConsentScreen />);
    expect(await screen.findByLabelText(/Photos OK/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Voice OK/)).toBeInTheDocument();
    expect(screen.getByLabelText(/AI processing OK/)).toBeInTheDocument();
    expect(screen.getByLabelText(/keep this data/i)).toBeInTheDocument();
  });

  it('toggling and saving calls upsert with the right payload', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ConsentScreen />);

    await user.click(await screen.findByLabelText(/Photos OK/));
    await user.click(screen.getByLabelText(/AI processing OK/));
    await user.selectOptions(screen.getByLabelText(/keep this data/i), '365');
    await user.click(screen.getByTestId('dci-consent-save'));

    await waitFor(() => expect(mockUpsert).toHaveBeenCalledTimes(1));
    expect(mockUpsert).toHaveBeenCalledWith({
      kid_id: 11,
      photo_ok: true,
      voice_ok: false,
      ai_ok: true,
      retention_days: 365,
    });
    await screen.findByTestId('dci-consent-saved');
  });

  it('shows the kid selector when more than one kid is linked', async () => {
    renderWithProviders(<ConsentScreen />);
    const select = await screen.findByLabelText('Kid');
    expect(select).toBeInTheDocument();
    // Both kids appear as options
    expect(screen.getByRole('option', { name: 'Haashini' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Arjun' })).toBeInTheDocument();
  });

  it('switching kid loads the new kid consent and saves to the new kid', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ConsentScreen />);

    await user.selectOptions(await screen.findByLabelText('Kid'), '12');
    await waitFor(() => expect(mockGet).toHaveBeenCalledWith(12));

    await user.click(screen.getByLabelText(/Voice OK/));
    await user.click(screen.getByTestId('dci-consent-save'));

    await waitFor(() => expect(mockUpsert).toHaveBeenCalledTimes(1));
    expect(mockUpsert.mock.calls[0][0].kid_id).toBe(12);
    expect(mockUpsert.mock.calls[0][0].voice_ok).toBe(true);
  });

  it('renders an empty state when the parent has no kids', async () => {
    mockGetChildren.mockResolvedValueOnce([]);
    renderWithProviders(<ConsentScreen />);
    expect(
      await screen.findByText(/don't have any kids linked yet/i),
    ).toBeInTheDocument();
  });
});
