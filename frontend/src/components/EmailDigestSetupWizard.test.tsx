import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor, fireEvent } from '@testing-library/react';
import { renderWithProviders } from '../test/helpers';
import { EmailDigestSetupWizard } from './EmailDigestSetupWizard';

const mockListIntegrations = vi.fn();
const mockUpdateIntegration = vi.fn();
const mockAddMonitoredEmail = vi.fn();
const mockUpdateSettings = vi.fn();
const mockListChildProfiles = vi.fn();
const mockCreateChildProfile = vi.fn();
const mockAddChildSchoolEmail = vi.fn();

vi.mock('../api/parentEmailDigest', async () => {
  const actual = await vi.importActual<typeof import('../api/parentEmailDigest')>(
    '../api/parentEmailDigest',
  );
  return {
    ...actual,
    listIntegrations: (...args: unknown[]) => mockListIntegrations(...args),
    updateIntegration: (...args: unknown[]) => mockUpdateIntegration(...args),
    addMonitoredEmail: (...args: unknown[]) => mockAddMonitoredEmail(...args),
    updateSettings: (...args: unknown[]) => mockUpdateSettings(...args),
    listChildProfiles: (...args: unknown[]) => mockListChildProfiles(...args),
    createChildProfile: (...args: unknown[]) => mockCreateChildProfile(...args),
    addChildSchoolEmail: (...args: unknown[]) => mockAddChildSchoolEmail(...args),
  };
});

const mockGetChildren = vi.fn();

vi.mock('../api/parent', async () => {
  const actual = await vi.importActual<typeof import('../api/parent')>(
    '../api/parent',
  );
  return {
    ...actual,
    parentApi: {
      ...(actual.parentApi ?? {}),
      getChildren: (...args: unknown[]) => mockGetChildren(...args),
    },
  };
});

const mockUseFeatureFlagEnabled = vi.fn<(key: string) => boolean>(() => false);

vi.mock('../hooks/useFeatureToggle', async () => {
  const actual = await vi.importActual<typeof import('../hooks/useFeatureToggle')>(
    '../hooks/useFeatureToggle',
  );
  return {
    ...actual,
    useFeatureFlagEnabled: (key: string) => mockUseFeatureFlagEnabled(key),
  };
});

beforeEach(() => {
  vi.clearAllMocks();
  mockUpdateIntegration.mockResolvedValue({ data: {} });
  mockAddMonitoredEmail.mockResolvedValue({ data: {} });
  mockUpdateSettings.mockResolvedValue({ data: {} });
  mockListChildProfiles.mockResolvedValue({ data: [] });
  mockCreateChildProfile.mockResolvedValue({ data: { id: 7001 } });
  mockAddChildSchoolEmail.mockResolvedValue({ data: {} });
  mockGetChildren.mockResolvedValue([]);
  mockUseFeatureFlagEnabled.mockReturnValue(false);
});

// Shared helper: seed a pre-existing integration so the wizard lands on Step 2
// after the initial lookup, avoiding the Gmail OAuth flow in tests.
function seedExistingIntegration() {
  mockListIntegrations.mockResolvedValue({
    data: [
      {
        id: 42,
        parent_id: 1,
        gmail_address: 'parent@example.com',
        google_id: 'g1',
        child_school_email: 'child@school.ca',
        child_first_name: 'Sam',
        connected_at: '2026-01-01T00:00:00Z',
        last_synced_at: null,
        is_active: true,
        paused_until: null,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        monitored_emails: [
          {
            id: 1,
            integration_id: 42,
            email_address: 'teacher@school.ca',
            sender_name: 'Mrs. Smith',
            label: 'Teacher',
            is_active: true,
            created_at: '2026-01-01T00:00:00Z',
          },
        ],
        whatsapp_phone: null,
        whatsapp_verified: false,
      },
    ],
  });
}

// Advance through Steps 2 -> 3 -> 4 so the wizard is parked on the Confirm
// step ready to transition into Step 5 when the v2 flag is ON.
async function advanceToStep4() {
  await waitFor(() => {
    expect(screen.getByText('Emails to Monitor')).toBeInTheDocument();
  });
  fireEvent.click(screen.getByRole('button', { name: 'Next' }));
  await waitFor(() => {
    expect(screen.getByText('Configure Your Digest')).toBeInTheDocument();
  });
  fireEvent.click(screen.getByRole('button', { name: 'Next' }));
  await waitFor(() => {
    expect(
      screen.getByRole('heading', { name: /Review/i }),
    ).toBeInTheDocument();
  });
}

// Factory for a test ChildSummary with Aarav Patel as Grade 10.
function buildKid(overrides: Record<string, unknown> = {}) {
  return {
    student_id: 11,
    user_id: 101,
    full_name: 'Aarav Patel',
    email: 'aarav@cb.ca',
    grade_level: 10,
    school_name: null,
    date_of_birth: null,
    phone: null,
    address: null,
    city: null,
    province: null,
    postal_code: null,
    notes: null,
    interests: [],
    relationship_type: 'guardian',
    invite_link: null,
    course_count: 0,
    active_task_count: 0,
    invite_status: 'active',
    invite_id: null,
    ...overrides,
  };
}

describe('EmailDigestSetupWizard — digest format options', () => {
  it('lists sectioned/full/brief/actions_only on Step 3 with sectioned as default', async () => {
    // Land the wizard on Step 2 by seeding an existing integration, then
    // advance to Step 3 so the Digest Format <select> renders.
    seedExistingIntegration();

    renderWithProviders(
      <EmailDigestSetupWizard
        open
        onClose={() => {}}
        childName="Sam"
      />,
    );

    // Step 2 is reached after the integration lookup.
    await waitFor(() => {
      expect(screen.getByText('Emails to Monitor')).toBeInTheDocument();
    });

    // Advance to Step 3 (no network call is made since integrationId + child
    // info are already populated by the lookup response — but the component
    // does call updateIntegration/addMonitoredEmail; catch those quietly).
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));

    await waitFor(() => {
      expect(screen.getByText('Configure Your Digest')).toBeInTheDocument();
    });

    const select = screen.getByLabelText('Digest Format') as HTMLSelectElement;
    const values = Array.from(select.options).map(o => o.value);

    expect(values).toEqual(['sectioned', 'full', 'brief', 'actions_only']);
    expect(select.value).toBe('sectioned');
  });
});

describe('EmailDigestSetupWizard — Step 5 school emails (flag-gated, #4017)', () => {
  it('step is NOT rendered when parent.unified_digest_v2 flag is OFF', async () => {
    mockUseFeatureFlagEnabled.mockReturnValue(false);
    seedExistingIntegration();

    renderWithProviders(
      <EmailDigestSetupWizard open onClose={() => {}} childName="Sam" />,
    );
    await advanceToStep4();

    // With the flag OFF, Step 4 is the final step — the button says
    // "Complete Setup" (not "Next") and there's no Step 5 school-emails prompt.
    expect(screen.getByRole('button', { name: 'Complete Setup' })).toBeInTheDocument();
    expect(
      screen.queryByText(/What are your kids/i),
    ).not.toBeInTheDocument();
  });

  it('step IS rendered when parent.unified_digest_v2 flag is ON', async () => {
    mockUseFeatureFlagEnabled.mockReturnValue(true);
    seedExistingIntegration();
    mockGetChildren.mockResolvedValue([buildKid()]);

    renderWithProviders(
      <EmailDigestSetupWizard open onClose={() => {}} childName="Sam" />,
    );
    await advanceToStep4();

    // Flag ON means Step 4's next button is just "Next"; advance to Step 5.
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));

    await waitFor(() => {
      expect(
        screen.getByText(/What are your kids.* school email/i),
      ).toBeInTheDocument();
    });
    // Kid label renders with first name + grade.
    await waitFor(() => {
      expect(screen.getByText(/Aarav/)).toBeInTheDocument();
    });
    expect(screen.getByText(/Grade 10/)).toBeInTheDocument();
    // Skip + Continue buttons exist.
    expect(screen.getByRole('button', { name: 'Skip' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Continue' })).toBeInTheDocument();
  });

  it('Skip moves past without any school-email API call', async () => {
    mockUseFeatureFlagEnabled.mockReturnValue(true);
    seedExistingIntegration();
    mockGetChildren.mockResolvedValue([buildKid()]);

    const onClose = vi.fn();
    const onComplete = vi.fn();
    renderWithProviders(
      <EmailDigestSetupWizard
        open
        onClose={onClose}
        onComplete={onComplete}
        childName="Sam"
      />,
    );
    await advanceToStep4();
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Skip' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Skip' }));

    await waitFor(() => {
      expect(onClose).toHaveBeenCalled();
    });
    // Neither the profile-resolve nor the email-save endpoints should be hit
    // when the parent skips the step.
    expect(mockListChildProfiles).not.toHaveBeenCalled();
    expect(mockCreateChildProfile).not.toHaveBeenCalled();
    expect(mockAddChildSchoolEmail).not.toHaveBeenCalled();
    expect(onComplete).toHaveBeenCalledWith(42);
  });

  it('filling a kid email POSTs to the right profile_id (reuses existing profile)', async () => {
    mockUseFeatureFlagEnabled.mockReturnValue(true);
    seedExistingIntegration();
    mockGetChildren.mockResolvedValue([buildKid()]);
    // Existing ParentChildProfile from Stream 1 backfill.
    mockListChildProfiles.mockResolvedValue({
      data: [
        {
          id: 555,
          parent_id: 1,
          student_id: 11,
          first_name: 'Aarav',
          created_at: '2026-04-23T00:00:00Z',
          school_emails: [],
        },
      ],
    });

    renderWithProviders(
      <EmailDigestSetupWizard open onClose={() => {}} childName="Sam" />,
    );
    await advanceToStep4();
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Continue' })).toBeInTheDocument();
    });
    // Wait for kids to load so the per-kid email input renders.
    const input = (await screen.findByLabelText(/Aarav/)) as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'aarav@school.ca' } });

    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));

    await waitFor(() => {
      expect(mockAddChildSchoolEmail).toHaveBeenCalledTimes(1);
    });
    expect(mockAddChildSchoolEmail).toHaveBeenCalledWith(555, 'aarav@school.ca');
    // No create call — the profile already existed.
    expect(mockCreateChildProfile).not.toHaveBeenCalled();
  });

  it('invalid email shows inline validation and does not submit', async () => {
    mockUseFeatureFlagEnabled.mockReturnValue(true);
    seedExistingIntegration();
    mockGetChildren.mockResolvedValue([buildKid()]);

    renderWithProviders(
      <EmailDigestSetupWizard open onClose={() => {}} childName="Sam" />,
    );
    await advanceToStep4();
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Continue' })).toBeInTheDocument();
    });
    const input = (await screen.findByLabelText(/Aarav/)) as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'not-an-email' } });

    fireEvent.click(screen.getByRole('button', { name: 'Continue' }));

    await waitFor(() => {
      expect(
        screen.getByText(/Please enter a valid email address/i),
      ).toBeInTheDocument();
    });
    expect(mockAddChildSchoolEmail).not.toHaveBeenCalled();
    expect(mockCreateChildProfile).not.toHaveBeenCalled();
  });
});
