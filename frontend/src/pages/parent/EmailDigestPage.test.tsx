import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ReactNode } from 'react';
import { screen, waitFor, fireEvent, within } from '@testing-library/react';
import { renderWithProviders } from '../../test/helpers';
import { EmailDigestPage } from './EmailDigestPage';
import type {
  EmailDigestIntegration,
  ChildProfile,
  MonitoredSender,
} from '../../api/parentEmailDigest';
import type { ChildSummary } from '../../api/parent';

const mockListIntegrations = vi.fn();
const mockGetSettings = vi.fn();
const mockGetLogs = vi.fn();
const mockListMonitoredEmails = vi.fn();
const mockSendWhatsAppOTP = vi.fn();
const mockVerifyWhatsAppOTP = vi.fn();
const mockDisconnectWhatsApp = vi.fn();
const mockSendDigestNow = vi.fn();
const mockSendDigestNowForParent = vi.fn();
const mockTriggerSync = vi.fn();
const mockListChildProfiles = vi.fn();
const mockCreateChildProfile = vi.fn();
const mockAddChildSchoolEmail = vi.fn();
const mockRemoveChildSchoolEmail = vi.fn();
const mockListMonitoredSenders = vi.fn();
const mockAddMonitoredSender = vi.fn();
const mockRemoveMonitoredSender = vi.fn();
const mockGetChildren = vi.fn();
const mockListDiscoveredSchoolEmails = vi.fn();
const mockAssignDiscoveredSchoolEmail = vi.fn();
const mockDismissDiscoveredSchoolEmail = vi.fn();

vi.mock('../../api/parentEmailDigest', async () => {
  const actual = await vi.importActual<typeof import('../../api/parentEmailDigest')>(
    '../../api/parentEmailDigest',
  );
  return {
    ...actual,
    listIntegrations: (...args: unknown[]) => mockListIntegrations(...args),
    getSettings: (...args: unknown[]) => mockGetSettings(...args),
    getLogs: (...args: unknown[]) => mockGetLogs(...args),
    listMonitoredEmails: (...args: unknown[]) => mockListMonitoredEmails(...args),
    sendWhatsAppOTP: (...args: unknown[]) => mockSendWhatsAppOTP(...args),
    verifyWhatsAppOTP: (...args: unknown[]) => mockVerifyWhatsAppOTP(...args),
    disconnectWhatsApp: (...args: unknown[]) => mockDisconnectWhatsApp(...args),
    sendDigestNow: (...args: unknown[]) => mockSendDigestNow(...args),
    sendDigestNowForParent: (...args: unknown[]) =>
      mockSendDigestNowForParent(...args),
    triggerSync: (...args: unknown[]) => mockTriggerSync(...args),
    listChildProfiles: (...args: unknown[]) => mockListChildProfiles(...args),
    createChildProfile: (...args: unknown[]) => mockCreateChildProfile(...args),
    addChildSchoolEmail: (...args: unknown[]) => mockAddChildSchoolEmail(...args),
    removeChildSchoolEmail: (...args: unknown[]) => mockRemoveChildSchoolEmail(...args),
    listMonitoredSenders: (...args: unknown[]) => mockListMonitoredSenders(...args),
    addMonitoredSender: (...args: unknown[]) => mockAddMonitoredSender(...args),
    removeMonitoredSender: (...args: unknown[]) => mockRemoveMonitoredSender(...args),
    listDiscoveredSchoolEmails: (...args: unknown[]) =>
      mockListDiscoveredSchoolEmails(...args),
    assignDiscoveredSchoolEmail: (...args: unknown[]) =>
      mockAssignDiscoveredSchoolEmail(...args),
    dismissDiscoveredSchoolEmail: (...args: unknown[]) =>
      mockDismissDiscoveredSchoolEmail(...args),
  };
});

vi.mock('../../api/parent', async () => {
  const actual = await vi.importActual<typeof import('../../api/parent')>(
    '../../api/parent',
  );
  return {
    ...actual,
    parentApi: {
      ...actual.parentApi,
      getChildren: (...args: unknown[]) => mockGetChildren(...args),
    },
  };
});

vi.mock('../../components/DashboardLayout', () => ({
  DashboardLayout: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="layout">{children}</div>
  ),
}));

// #4349 Stream E: DigestHistoryPanel was extracted into a shared component.
// Stub it here so EmailDigestPage tests stay focused on page-level wiring;
// the panel's own behavior (loading/empty/expand/sanitize) is covered by
// `frontend/src/components/parent/DigestHistoryPanel.test.tsx`.
vi.mock('../../components/parent/DigestHistoryPanel', () => ({
  DigestHistoryPanel: ({ limit, emptyState }: { limit?: number; emptyState?: ReactNode }) => (
    <div
      data-testid="digest-history-panel"
      data-limit={String(limit ?? '')}
      data-empty-state={typeof emptyState === 'string' ? emptyState : ''}
    >
      Digest History
    </div>
  ),
}));

let confirmResolveValue = true;
vi.mock('../../components/ConfirmModal', () => ({
  useConfirm: () => ({
    confirm: () => Promise.resolve(confirmResolveValue),
    confirmModal: null,
    getLastPromptValue: () => '',
  }),
}));

// Feature-flag mock — default OFF (legacy UI). Individual tests override via
// `flagEnabledMock.mockReturnValue(true)` to exercise the unified branch.
//
// CB-EDIGEST-002 (#4594): the `email_digest_dashboard_v1` flag is force-OFF
// in this test suite so the existing unified-page tests keep exercising the
// list UI. The dashboard branch has its own coverage in
// `pages/parent/dashboard/DashboardView.test.tsx`. Tests that need the
// dashboard branch can override via `dashboardFlagMock.mockReturnValue(true)`.
const flagEnabledMock = vi.fn<(key: string) => boolean>(() => false);
const dashboardFlagMock = vi.fn<(key: string) => boolean>(() => false);
vi.mock('../../hooks/useFeatureToggle', async () => {
  const actual = await vi.importActual<typeof import('../../hooks/useFeatureToggle')>(
    '../../hooks/useFeatureToggle',
  );
  return {
    ...actual,
    useFeatureFlagEnabled: (key: string) => {
      if (key === 'email_digest_dashboard_v1') {
        return dashboardFlagMock(key);
      }
      return flagEnabledMock(key);
    },
  };
});

// Stub DashboardView so flag-gate tests don't pull in its API queries.
vi.mock('./dashboard/DashboardView', () => ({
  DashboardView: () => <div data-testid="dashboard-view-stub" />,
}));

function buildIntegration(overrides: Partial<EmailDigestIntegration> = {}): EmailDigestIntegration {
  return {
    id: 1,
    parent_id: 100,
    gmail_address: 'parent@example.com',
    google_id: 'g123',
    child_school_email: 'child@school.ca',
    child_first_name: 'Sam',
    connected_at: '2026-01-01T00:00:00Z',
    last_synced_at: '2026-04-01T00:00:00Z',
    is_active: true,
    paused_until: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-04-01T00:00:00Z',
    monitored_emails: [],
    whatsapp_phone: null,
    whatsapp_verified: false,
    ...overrides,
  };
}

function buildChildProfile(overrides: Partial<ChildProfile> = {}): ChildProfile {
  return {
    id: 11,
    parent_id: 100,
    student_id: 500,
    first_name: 'Thanushan',
    school_emails: [],
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-04-01T00:00:00Z',
    ...overrides,
  };
}

function buildKid(overrides: Partial<ChildSummary> = {}): ChildSummary {
  return {
    student_id: 9001,
    user_id: 500,
    full_name: 'Thanushan Last',
    email: 'thanushan@example.com',
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
    relationship_type: 'guardian',
    invite_link: null,
    course_count: 0,
    active_task_count: 0,
    invite_status: 'active',
    invite_id: null,
    ...overrides,
  };
}

function buildSender(overrides: Partial<MonitoredSender> = {}): MonitoredSender {
  return {
    id: 201,
    parent_id: 100,
    email_address: 'teacher@school.ca',
    sender_name: null,
    label: null,
    applies_to_all: true,
    child_profile_ids: [],
    assignments: [],
    created_at: '2026-04-01T00:00:00Z',
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  confirmResolveValue = true;
  flagEnabledMock.mockReturnValue(false);
  dashboardFlagMock.mockReturnValue(false);
  mockGetSettings.mockResolvedValue({
    data: {
      id: 1,
      integration_id: 1,
      digest_enabled: true,
      delivery_time: '07:00',
      timezone: 'America/Toronto',
      digest_format: 'html',
      delivery_channels: 'in_app,email',
      notify_on_empty: false,
      updated_at: '2026-04-01T00:00:00Z',
    },
  });
  mockGetLogs.mockResolvedValue({ data: [] });
  mockListMonitoredEmails.mockResolvedValue({ data: [] });
  mockListChildProfiles.mockResolvedValue({ data: [] });
  mockListMonitoredSenders.mockResolvedValue({ data: [] });
  // #4329: default — no auto-discovered school addresses. Tests that
  // care about discovery rows override this.
  mockListDiscoveredSchoolEmails.mockResolvedValue({ data: [] });
  mockAssignDiscoveredSchoolEmail.mockResolvedValue({ data: { status: 'ok' } });
  mockDismissDiscoveredSchoolEmail.mockResolvedValue({ data: undefined });
  // #4044: default — parent has no kids in the People-API list. Tests that
  // care about kid rows override this with mockGetChildren.mockResolvedValue.
  mockGetChildren.mockResolvedValue([]);
});

describe('EmailDigestPage — WhatsApp section', () => {
  it('renders "Send OTP" button when WhatsApp not connected', async () => {
    mockListIntegrations.mockResolvedValue({ data: [buildIntegration()] });
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByText('Receive Digest on WhatsApp')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: 'Send OTP' })).toBeInTheDocument();
    expect(screen.getByPlaceholderText('+14165551234')).toBeInTheDocument();
  });

  it('calls sendWhatsAppOTP when "Send OTP" clicked with valid phone', async () => {
    mockListIntegrations.mockResolvedValue({ data: [buildIntegration()] });
    mockSendWhatsAppOTP.mockResolvedValue({ message: 'OTP sent', phone: '+14165551234' });
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByPlaceholderText('+14165551234')).toBeInTheDocument();
    });

    const phoneInput = screen.getByPlaceholderText('+14165551234') as HTMLInputElement;
    fireEvent.change(phoneInput, { target: { value: '+14165551234' } });

    const sendBtn = screen.getByRole('button', { name: 'Send OTP' });
    fireEvent.click(sendBtn);

    await waitFor(() => {
      expect(mockSendWhatsAppOTP).toHaveBeenCalledWith(1, '+14165551234');
    });
  });

  it('shows validation error when phone is invalid', async () => {
    mockListIntegrations.mockResolvedValue({ data: [buildIntegration()] });
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByPlaceholderText('+14165551234')).toBeInTheDocument();
    });

    const phoneInput = screen.getByPlaceholderText('+14165551234') as HTMLInputElement;
    fireEvent.change(phoneInput, { target: { value: '4165551234' } }); // missing +

    const sendBtn = screen.getByRole('button', { name: 'Send OTP' });
    fireEvent.click(sendBtn);

    await waitFor(() => {
      expect(screen.getByText(/E\.164 format/)).toBeInTheDocument();
    });
    expect(mockSendWhatsAppOTP).not.toHaveBeenCalled();
  });

  it('shows OTP verification form when phone set but not verified', async () => {
    mockListIntegrations.mockResolvedValue({
      data: [buildIntegration({ whatsapp_phone: '+14165551234', whatsapp_verified: false })],
    });
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByText(/Code sent to/)).toBeInTheDocument();
    });
    expect(screen.getByText('+14165551234')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('6-digit code')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Verify' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Resend code' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
  });

  it('calls verifyWhatsAppOTP when "Verify" clicked', async () => {
    mockListIntegrations.mockResolvedValue({
      data: [buildIntegration({ whatsapp_phone: '+14165551234', whatsapp_verified: false })],
    });
    mockVerifyWhatsAppOTP.mockResolvedValue({ message: 'verified', phone: '+14165551234' });
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByPlaceholderText('6-digit code')).toBeInTheDocument();
    });

    const otpInput = screen.getByPlaceholderText('6-digit code') as HTMLInputElement;
    fireEvent.change(otpInput, { target: { value: '123456' } });

    const verifyBtn = screen.getByRole('button', { name: 'Verify' });
    fireEvent.click(verifyBtn);

    await waitFor(() => {
      expect(mockVerifyWhatsAppOTP).toHaveBeenCalledWith(1, '123456');
    });
  });

  it('shows "WhatsApp connected" state when verified', async () => {
    mockListIntegrations.mockResolvedValue({
      data: [buildIntegration({ whatsapp_phone: '+14165551234', whatsapp_verified: true })],
    });
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByText(/WhatsApp connected:/)).toBeInTheDocument();
    });
    expect(screen.getByText('+14165551234')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Disconnect' })).toBeInTheDocument();
    expect(
      screen.getByText('Your daily digest will be delivered to this number.'),
    ).toBeInTheDocument();
  });

  it('calls disconnectWhatsApp when "Disconnect" clicked', async () => {
    mockListIntegrations.mockResolvedValue({
      data: [buildIntegration({ whatsapp_phone: '+14165551234', whatsapp_verified: true })],
    });
    mockDisconnectWhatsApp.mockResolvedValue(undefined);
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Disconnect' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Disconnect' }));

    await waitFor(() => {
      expect(mockDisconnectWhatsApp).toHaveBeenCalledWith(1);
    });
  });

  it('calls disconnectWhatsApp when "Cancel" clicked in pending state', async () => {
    mockListIntegrations.mockResolvedValue({
      data: [buildIntegration({ whatsapp_phone: '+14165551234', whatsapp_verified: false })],
    });
    mockDisconnectWhatsApp.mockResolvedValue(undefined);
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));

    await waitFor(() => {
      expect(mockDisconnectWhatsApp).toHaveBeenCalledWith(1);
    });
  });

  it('does NOT call disconnectWhatsApp when user cancels confirmation', async () => {
    confirmResolveValue = false;
    mockListIntegrations.mockResolvedValue({
      data: [buildIntegration({ whatsapp_phone: '+14165551234', whatsapp_verified: false })],
    });
    mockDisconnectWhatsApp.mockResolvedValue(undefined);
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));

    // Wait a microtask for the confirm promise to resolve
    await waitFor(() => {
      // Confirmation rejected, so disconnect should not have been called
      expect(mockDisconnectWhatsApp).not.toHaveBeenCalled();
    });
  });

  it('calls sendWhatsAppOTP with saved phone when "Resend code" clicked', async () => {
    mockListIntegrations.mockResolvedValue({
      data: [buildIntegration({ whatsapp_phone: '+14165551234', whatsapp_verified: false })],
    });
    mockSendWhatsAppOTP.mockResolvedValue({ message: 'OTP sent', phone: '+14165551234' });
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Resend code' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Resend code' }));

    await waitFor(() => {
      expect(mockSendWhatsAppOTP).toHaveBeenCalledWith(1, '+14165551234');
    });
  });

  it('shows API error message when send-otp fails', async () => {
    mockListIntegrations.mockResolvedValue({ data: [buildIntegration()] });
    mockSendWhatsAppOTP.mockRejectedValue({
      response: { data: { detail: 'Rate limit exceeded' } },
    });
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByPlaceholderText('+14165551234')).toBeInTheDocument();
    });

    const phoneInput = screen.getByPlaceholderText('+14165551234') as HTMLInputElement;
    fireEvent.change(phoneInput, { target: { value: '+14165551234' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send OTP' }));

    await waitFor(() => {
      expect(screen.getByText('Rate limit exceeded')).toBeInTheDocument();
    });
  });
});

// #3880: Per-channel delivery status — three variants of the Send Digest Now toast.
describe('EmailDigestPage — per-channel digest status (#3880)', () => {
  it('renders green delivered status on success', async () => {
    mockListIntegrations.mockResolvedValue({ data: [buildIntegration()] });
    mockSendDigestNow.mockResolvedValue({
      data: {
        status: 'delivered',
        email_count: 3,
        message: 'Digest delivered with 3 emails',
        channel_status: { in_app: true, email: true, whatsapp: null },
      },
    });

    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Send Digest Now' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Send Digest Now' }));

    await waitFor(() => {
      expect(screen.getByText('Digest delivered with 3 emails')).toBeInTheDocument();
    });
    const banner = screen.getByText('Digest delivered with 3 emails').closest(
      '.ed-digest-status',
    ) as HTMLElement;
    expect(banner).not.toBeNull();
    expect(banner.className).toContain('ed-digest-status--delivered');
    expect(banner.getAttribute('data-status')).toBe('delivered');
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument();
  });

  it('renders amber partial status with failed-channel list', async () => {
    mockListIntegrations.mockResolvedValue({ data: [buildIntegration()] });
    mockSendDigestNow.mockResolvedValue({
      data: {
        status: 'partial',
        email_count: 2,
        message:
          'Digest partially delivered (2 emails). Failed channels: WhatsApp. Check your setup.',
        channel_status: { in_app: true, email: true, whatsapp: false },
      },
    });

    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Send Digest Now' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Send Digest Now' }));

    await waitFor(() => {
      expect(screen.getByText(/Digest partially delivered/)).toBeInTheDocument();
    });
    const banner = screen.getByText(/Digest partially delivered/).closest(
      '.ed-digest-status',
    ) as HTMLElement;
    expect(banner).not.toBeNull();
    expect(banner.className).toContain('ed-digest-status--partial');
    expect(banner.getAttribute('data-status')).toBe('partial');
    expect(banner.textContent).toContain('WhatsApp');
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument();
  });

  it('renders red failed status with a Try again retry button', async () => {
    mockListIntegrations.mockResolvedValue({ data: [buildIntegration()] });
    mockSendDigestNow.mockResolvedValue({
      data: {
        status: 'failed',
        email_count: 2,
        message:
          'Digest delivery failed on all channels (2 emails). Please try again or check your setup.',
        channel_status: { in_app: false, email: false, whatsapp: null },
      },
    });

    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Send Digest Now' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Send Digest Now' }));

    await waitFor(() => {
      expect(screen.getByText(/failed on all channels/)).toBeInTheDocument();
    });
    const banner = screen.getByText(/failed on all channels/).closest(
      '.ed-digest-status',
    ) as HTMLElement;
    expect(banner).not.toBeNull();
    expect(banner.className).toContain('ed-digest-status--failed');
    expect(banner.getAttribute('data-status')).toBe('failed');

    const retryBtn = screen.getByRole('button', { name: 'Try again' });
    expect(retryBtn).toBeInTheDocument();

    mockSendDigestNow.mockClear();
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(mockSendDigestNow).toHaveBeenCalledWith(1);
    });
  });
});

// #3887: skipped status — every selected channel intentionally skipped
// (preference off / WhatsApp unverified). No retry CTA, info-style banner,
// link to preferences (#3894: only when reason="no_eligible_channels").
describe('EmailDigestPage — skipped digest status (#3887, #3894)', () => {
  it('renders info-style skipped status with preferences link for reason=no_eligible_channels', async () => {
    mockListIntegrations.mockResolvedValue({ data: [buildIntegration()] });
    mockSendDigestNow.mockResolvedValue({
      data: {
        status: 'skipped',
        email_count: 2,
        message:
          'No eligible channels (2 emails). Please verify WhatsApp or enable notifications in your preferences.',
        channel_status: { in_app: null, email: null, whatsapp: null },
        reason: 'no_eligible_channels',
      },
    });

    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Send Digest Now' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Send Digest Now' }));

    await waitFor(() => {
      expect(screen.getByText(/No eligible channels/)).toBeInTheDocument();
    });
    const banner = screen.getByText(/No eligible channels/).closest(
      '.ed-digest-status',
    ) as HTMLElement;
    expect(banner).not.toBeNull();
    expect(banner.className).toContain('ed-digest-status--skipped');
    expect(banner.getAttribute('data-status')).toBe('skipped');

    // No retry CTA for skipped — retrying won't help; parent must fix prefs.
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument();

    // Preferences link points to /settings/notifications.
    const prefsLink = screen.getByRole('link', { name: 'Open preferences' });
    expect(prefsLink).toBeInTheDocument();
    expect(prefsLink.getAttribute('href')).toBe('/settings/notifications');
  });

  it('does NOT render preferences link for skipped with reason=no_new_emails (#3894)', async () => {
    mockListIntegrations.mockResolvedValue({ data: [buildIntegration()] });
    mockSendDigestNow.mockResolvedValue({
      data: {
        status: 'skipped',
        email_count: 0,
        message: 'No new emails',
        channel_status: { in_app: null, email: null, whatsapp: null },
        reason: 'no_new_emails',
      },
    });

    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Send Digest Now' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Send Digest Now' }));

    await waitFor(() => {
      expect(screen.getByText('No new emails')).toBeInTheDocument();
    });

    // "Open preferences" is meaningful only when the channels themselves
    // were ineligible — not when there was nothing to deliver.
    expect(screen.queryByRole('link', { name: 'Open preferences' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument();
  });
});

// ============================================================================
// Unified multi-kid Email Digest v2 (#4016)
// ============================================================================
describe('EmailDigestPage — flag gate (unified v2, #4016)', () => {
  it('renders legacy UI when parent.unified_digest_v2 is OFF', async () => {
    flagEnabledMock.mockReturnValue(false);
    mockListIntegrations.mockResolvedValue({ data: [buildIntegration()] });

    renderWithProviders(<EmailDigestPage />);

    await waitFor(() => {
      // "Quick Settings" card header is unique to legacy layout.
      expect(screen.getByText('Quick Settings')).toBeInTheDocument();
    });
    expect(screen.queryByText('Your kids')).not.toBeInTheDocument();
    expect(screen.queryByText('Monitored senders')).not.toBeInTheDocument();
  });

  it('renders unified UI when parent.unified_digest_v2 is ON', async () => {
    flagEnabledMock.mockReturnValue(true);
    mockListIntegrations.mockResolvedValue({ data: [buildIntegration()] });
    mockListChildProfiles.mockResolvedValue({ data: [buildChildProfile()] });
    mockListMonitoredSenders.mockResolvedValue({ data: [] });

    renderWithProviders(<EmailDigestPage />);

    await waitFor(() => {
      expect(screen.getByText('Your kids')).toBeInTheDocument();
    });
    expect(screen.getByText('Monitored senders')).toBeInTheDocument();
    // Legacy-only heading absent in unified.
    expect(screen.queryByText('Quick Settings')).not.toBeInTheDocument();
  });

  it('?legacy=1 forces legacy UI even when flag is ON', async () => {
    flagEnabledMock.mockReturnValue(true);
    mockListIntegrations.mockResolvedValue({ data: [buildIntegration()] });

    renderWithProviders(<EmailDigestPage />, { initialEntries: ['/email-digest?legacy=1'] });

    await waitFor(() => {
      expect(screen.getByText('Quick Settings')).toBeInTheDocument();
    });
    expect(screen.queryByText('Your kids')).not.toBeInTheDocument();
  });
});

describe('EmailDigestPage — unified forwarding-detected badges', () => {
  beforeEach(() => {
    flagEnabledMock.mockReturnValue(true);
    mockListIntegrations.mockResolvedValue({ data: [buildIntegration()] });
  });

  it('shows "Forwarding active" when forwarding_seen_at is within 14 days', async () => {
    const recent = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString();
    mockListChildProfiles.mockResolvedValue({
      data: [
        buildChildProfile({
          school_emails: [
            {
              id: 1,
              child_profile_id: 11,
              email_address: 'kid@ocdsb.ca',
              forwarding_seen_at: recent,
              created_at: '2026-04-01T00:00:00Z',
            },
          ],
        }),
      ],
    });

    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByText(/Forwarding active/)).toBeInTheDocument();
    });
  });

  it('shows "Forwarding may have stopped" when forwarding_seen_at is older than 14 days', async () => {
    const old = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();
    mockListChildProfiles.mockResolvedValue({
      data: [
        buildChildProfile({
          school_emails: [
            {
              id: 1,
              child_profile_id: 11,
              email_address: 'kid@ocdsb.ca',
              forwarding_seen_at: old,
              created_at: '2026-04-01T00:00:00Z',
            },
          ],
        }),
      ],
    });

    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByText(/Forwarding may have stopped/)).toBeInTheDocument();
    });
  });

  it('shows "No forwarded messages yet" when forwarding_seen_at is null', async () => {
    mockListChildProfiles.mockResolvedValue({
      data: [
        buildChildProfile({
          school_emails: [
            {
              id: 1,
              child_profile_id: 11,
              email_address: 'kid@ocdsb.ca',
              forwarding_seen_at: null,
              created_at: '2026-04-01T00:00:00Z',
            },
          ],
        }),
      ],
    });

    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByText(/No forwarded messages yet/)).toBeInTheDocument();
    });
  });
});

describe('EmailDigestPage — unified sender chips', () => {
  beforeEach(() => {
    flagEnabledMock.mockReturnValue(true);
    mockListIntegrations.mockResolvedValue({ data: [buildIntegration()] });
    mockListChildProfiles.mockResolvedValue({
      data: [
        buildChildProfile({ id: 11, first_name: 'Thanushan' }),
        buildChildProfile({ id: 12, first_name: 'Haashini' }),
      ],
    });
  });

  it('renders one chip per assigned kid for a multi-kid sender', async () => {
    mockListMonitoredSenders.mockResolvedValue({
      data: [
        buildSender({
          id: 201,
          email_address: 'principal@school.ca',
          applies_to_all: false,
          assignments: [
            { child_profile_id: 11, first_name: 'Thanushan' },
            { child_profile_id: 12, first_name: 'Haashini' },
          ],
        }),
      ],
    });

    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByText('principal@school.ca')).toBeInTheDocument();
    });
    const row = screen.getByText('principal@school.ca').closest('.ed-sender-row') as HTMLElement;
    expect(row).not.toBeNull();
    const chips = within(row).getAllByText(/Thanushan|Haashini/);
    // One chip per assignment (may include in-modal render if open — but modal
    // is not open here, so exactly 2).
    expect(chips).toHaveLength(2);
    expect(within(row).queryByText('All kids')).not.toBeInTheDocument();
  });

  // #4082: pre-#4082 backends returned only child_profile_ids; guard against
  // a stale cached response crashing with `undefined.map`.
  it('renders chips from child_profile_ids when assignments is missing', async () => {
    mockListChildProfiles.mockResolvedValue({
      data: [
        buildChildProfile({ id: 11, first_name: 'Thanushan' }),
        buildChildProfile({ id: 12, first_name: 'Haashini' }),
      ],
    });
    mockListMonitoredSenders.mockResolvedValue({
      data: [
        {
          ...buildSender({
            id: 203,
            email_address: 'legacy@school.ca',
            applies_to_all: false,
            child_profile_ids: [11, 12],
          }),
          // Simulate pre-#4082 response shape: no `assignments` field.
          assignments: undefined,
        } as unknown as MonitoredSender,
      ],
    });

    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByText('legacy@school.ca')).toBeInTheDocument();
    });
    const row = screen.getByText('legacy@school.ca').closest('.ed-sender-row') as HTMLElement;
    expect(row).not.toBeNull();
    expect(within(row).getByText('Thanushan')).toBeInTheDocument();
    expect(within(row).getByText('Haashini')).toBeInTheDocument();
  });

  // #4093: empty assignments is a valid "0 kids" response — do NOT fall
  // through to child_profile_ids. Only undefined triggers the fallback.
  it('does not fall through to child_profile_ids when assignments=[] (valid empty)', async () => {
    mockListChildProfiles.mockResolvedValue({
      data: [
        buildChildProfile({ id: 11, first_name: 'Thanushan' }),
        buildChildProfile({ id: 12, first_name: 'Haashini' }),
      ],
    });
    mockListMonitoredSenders.mockResolvedValue({
      data: [
        buildSender({
          id: 204,
          email_address: 'orphan@school.ca',
          applies_to_all: false,
          // Drift between child_profile_ids and assignments would normally
          // never happen — but if it did, we trust assignments when present.
          child_profile_ids: [11, 12],
          assignments: [],
        }),
      ],
    });

    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByText('orphan@school.ca')).toBeInTheDocument();
    });
    const row = screen.getByText('orphan@school.ca').closest('.ed-sender-row') as HTMLElement;
    expect(row).not.toBeNull();
    expect(within(row).queryByText('Thanushan')).not.toBeInTheDocument();
    expect(within(row).queryByText('Haashini')).not.toBeInTheDocument();
  });

  it('renders a single "All kids" chip when applies_to_all=true', async () => {
    mockListMonitoredSenders.mockResolvedValue({
      data: [
        buildSender({
          id: 202,
          email_address: 'board@district.ca',
          applies_to_all: true,
          assignments: [],
        }),
      ],
    });

    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByText('board@district.ca')).toBeInTheDocument();
    });
    const row = screen.getByText('board@district.ca').closest('.ed-sender-row') as HTMLElement;
    expect(row).not.toBeNull();
    expect(within(row).getByText('All kids')).toBeInTheDocument();
  });
});

describe('EmailDigestPage — unified add-sender modal', () => {
  beforeEach(() => {
    flagEnabledMock.mockReturnValue(true);
    mockListIntegrations.mockResolvedValue({ data: [buildIntegration()] });
    mockListChildProfiles.mockResolvedValue({
      data: [
        buildChildProfile({ id: 11, first_name: 'Thanushan' }),
        buildChildProfile({ id: 12, first_name: 'Haashini' }),
      ],
    });
    mockListMonitoredSenders.mockResolvedValue({ data: [] });
  });

  it('opens modal with "All kids" checkbox default-checked', async () => {
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /\+ Add sender/ })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /\+ Add sender/ }));

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
    const checkbox = screen.getByRole('checkbox', { name: /All kids/ }) as HTMLInputElement;
    expect(checkbox.checked).toBe(true);
  });

  it('blocks submit with validation error when all-kids unchecked AND no kids selected', async () => {
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /\+ Add sender/ })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /\+ Add sender/ }));
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    // Valid email but no kid selected.
    const emailInput = screen.getByPlaceholderText('teacher@school.ca') as HTMLInputElement;
    fireEvent.change(emailInput, { target: { value: 'teacher@school.ca' } });

    // Uncheck "All kids".
    fireEvent.click(screen.getByRole('checkbox', { name: /All kids/ }));

    // Submit without selecting any kid chip.
    fireEvent.click(screen.getByRole('button', { name: 'Add sender' }));

    await waitFor(() => {
      expect(screen.getByText(/Select at least one kid/)).toBeInTheDocument();
    });
    expect(mockAddMonitoredSender).not.toHaveBeenCalled();
  });

  it('submits with child_profile_ids when a kid chip is selected', async () => {
    mockAddMonitoredSender.mockResolvedValue({
      data: buildSender({ id: 300, email_address: 'teacher@school.ca' }),
    });

    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /\+ Add sender/ })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /\+ Add sender/ }));
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText('teacher@school.ca'), {
      target: { value: 'teacher@school.ca' },
    });
    fireEvent.click(screen.getByRole('checkbox', { name: /All kids/ }));
    // Chip toggle (pressed state via aria-pressed).
    fireEvent.click(screen.getByRole('button', { name: 'Thanushan', pressed: false }));

    fireEvent.click(screen.getByRole('button', { name: 'Add sender' }));

    await waitFor(() => {
      expect(mockAddMonitoredSender).toHaveBeenCalled();
    });
    const [[payload]] = mockAddMonitoredSender.mock.calls;
    expect(payload).toMatchObject({
      email_address: 'teacher@school.ca',
      child_profile_ids: [11],
    });
  });

  it('submits with child_profile_ids="all" when All kids remains checked', async () => {
    mockAddMonitoredSender.mockResolvedValue({
      data: buildSender({ id: 301, email_address: 'board@school.ca' }),
    });

    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /\+ Add sender/ })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /\+ Add sender/ }));
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText('teacher@school.ca'), {
      target: { value: 'board@school.ca' },
    });

    fireEvent.click(screen.getByRole('button', { name: 'Add sender' }));

    await waitFor(() => {
      expect(mockAddMonitoredSender).toHaveBeenCalled();
    });
    const [[payload]] = mockAddMonitoredSender.mock.calls;
    expect(payload).toMatchObject({
      email_address: 'board@school.ca',
      child_profile_ids: 'all',
    });
  });
});

// #4327: edit-mode regression tests — Add/Edit modal reuse for monitored senders.
describe('EmailDigestPage — edit monitored sender (#4327)', () => {
  beforeEach(() => {
    flagEnabledMock.mockReturnValue(true);
    mockListIntegrations.mockResolvedValue({ data: [buildIntegration()] });
    mockListChildProfiles.mockResolvedValue({
      data: [
        buildChildProfile({ id: 11, first_name: 'Thanushan' }),
        buildChildProfile({ id: 12, first_name: 'Haashini' }),
      ],
    });
  });

  it('renders Edit button for each monitored sender row', async () => {
    mockListMonitoredSenders.mockResolvedValue({
      data: [
        buildSender({
          id: 201,
          email_address: 'teacher@school.ca',
          applies_to_all: true,
        }),
        buildSender({
          id: 202,
          email_address: 'principal@school.ca',
          applies_to_all: true,
        }),
      ],
    });

    renderWithProviders(<EmailDigestPage />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: 'Edit teacher@school.ca' }),
      ).toBeInTheDocument();
    });
    expect(
      screen.getByRole('button', { name: 'Edit principal@school.ca' }),
    ).toBeInTheDocument();
  });

  it('opens modal pre-filled with the sender data; email field is read-only', async () => {
    mockListMonitoredSenders.mockResolvedValue({
      data: [
        buildSender({
          id: 201,
          email_address: 'teacher@school.ca',
          sender_name: 'Mrs. Smith',
          label: 'Homeroom',
          applies_to_all: false,
          child_profile_ids: [11],
          assignments: [{ child_profile_id: 11, first_name: 'Thanushan' }],
        }),
      ],
    });

    renderWithProviders(<EmailDigestPage />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: 'Edit teacher@school.ca' }),
      ).toBeInTheDocument();
    });

    fireEvent.click(
      screen.getByRole('button', { name: 'Edit teacher@school.ca' }),
    );

    await waitFor(() => {
      expect(
        screen.getByRole('dialog', { name: 'Edit monitored sender' }),
      ).toBeInTheDocument();
    });

    const dialog = screen.getByRole('dialog', { name: 'Edit monitored sender' });
    const emailInput = within(dialog).getByPlaceholderText(
      'teacher@school.ca',
    ) as HTMLInputElement;
    expect(emailInput.value).toBe('teacher@school.ca');
    expect(emailInput.readOnly).toBe(true);

    const nameInput = within(dialog).getByPlaceholderText(
      'Mrs. Smith',
    ) as HTMLInputElement;
    expect(nameInput.value).toBe('Mrs. Smith');

    const labelInput = within(dialog).getByPlaceholderText(
      'Homeroom, Principal, etc.',
    ) as HTMLInputElement;
    expect(labelInput.value).toBe('Homeroom');

    const allKidsCheckbox = within(dialog).getByRole('checkbox', {
      name: /All kids/,
    }) as HTMLInputElement;
    expect(allKidsCheckbox.checked).toBe(false);

    expect(
      within(dialog).getByRole('button', { name: 'Thanushan', pressed: true }),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByRole('button', { name: 'Haashini', pressed: false }),
    ).toBeInTheDocument();

    expect(
      within(dialog).getByRole('button', { name: 'Save changes' }),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByText(/To change the email/),
    ).toBeInTheDocument();
  });

  it('submits the edit through addMonitoredSender with updated kid assignments', async () => {
    mockListMonitoredSenders.mockResolvedValue({
      data: [
        buildSender({
          id: 201,
          email_address: 'teacher@school.ca',
          applies_to_all: true,
          child_profile_ids: [],
          assignments: [],
        }),
      ],
    });
    mockAddMonitoredSender.mockResolvedValue({
      data: buildSender({
        id: 201,
        email_address: 'teacher@school.ca',
        applies_to_all: false,
        child_profile_ids: [12],
      }),
    });

    renderWithProviders(<EmailDigestPage />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: 'Edit teacher@school.ca' }),
      ).toBeInTheDocument();
    });

    fireEvent.click(
      screen.getByRole('button', { name: 'Edit teacher@school.ca' }),
    );

    await waitFor(() => {
      expect(
        screen.getByRole('dialog', { name: 'Edit monitored sender' }),
      ).toBeInTheDocument();
    });

    const dialog = screen.getByRole('dialog', { name: 'Edit monitored sender' });

    fireEvent.click(within(dialog).getByRole('checkbox', { name: /All kids/ }));
    fireEvent.click(
      within(dialog).getByRole('button', { name: 'Haashini', pressed: false }),
    );
    fireEvent.click(within(dialog).getByRole('button', { name: 'Save changes' }));

    await waitFor(() => {
      expect(mockAddMonitoredSender).toHaveBeenCalled();
    });
    const [[payload]] = mockAddMonitoredSender.mock.calls;
    expect(payload).toMatchObject({
      email_address: 'teacher@school.ca',
      child_profile_ids: [12],
    });
  });

  it('cancel closes the modal without calling the API', async () => {
    mockListMonitoredSenders.mockResolvedValue({
      data: [
        buildSender({
          id: 201,
          email_address: 'teacher@school.ca',
          applies_to_all: true,
        }),
      ],
    });

    renderWithProviders(<EmailDigestPage />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: 'Edit teacher@school.ca' }),
      ).toBeInTheDocument();
    });

    fireEvent.click(
      screen.getByRole('button', { name: 'Edit teacher@school.ca' }),
    );

    await waitFor(() => {
      expect(
        screen.getByRole('dialog', { name: 'Edit monitored sender' }),
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));

    await waitFor(() => {
      expect(
        screen.queryByRole('dialog', { name: 'Edit monitored sender' }),
      ).not.toBeInTheDocument();
    });
    expect(mockAddMonitoredSender).not.toHaveBeenCalled();
  });
});

// #4007: multi-kid routing — clicking Email Digest for a specific kid must land on that kid.
describe('EmailDigestPage — multi-kid routing (#4007)', () => {
  const twoKids = [
    buildIntegration({ id: 1, child_first_name: 'Thanushan', child_school_email: 't@school.ca' }),
    buildIntegration({ id: 2, child_first_name: 'Haashini', child_school_email: 'h@school.ca' }),
  ];

  it('selects the integration matching ?kid= param, not integrations[0]', async () => {
    mockListIntegrations.mockResolvedValue({ data: twoKids });
    renderWithProviders(<EmailDigestPage />, { initialEntries: ['/email-digest?kid=Haashini'] });
    await waitFor(() => {
      expect(screen.getByText('for Haashini')).toBeInTheDocument();
    });
    expect(screen.queryByText('for Thanushan')).not.toBeInTheDocument();
  });

  it('matches kid name case-insensitively', async () => {
    mockListIntegrations.mockResolvedValue({ data: twoKids });
    renderWithProviders(<EmailDigestPage />, { initialEntries: ['/email-digest?kid=haashini'] });
    await waitFor(() => {
      expect(screen.getByText('for Haashini')).toBeInTheDocument();
    });
  });

  it('falls back to the first integration when ?kid= is missing', async () => {
    mockListIntegrations.mockResolvedValue({ data: twoKids });
    renderWithProviders(<EmailDigestPage />, { initialEntries: ['/email-digest'] });
    await waitFor(() => {
      expect(screen.getByText('for Thanushan')).toBeInTheDocument();
    });
  });

  it('falls back to the first integration when ?kid= does not match any child', async () => {
    mockListIntegrations.mockResolvedValue({ data: twoKids });
    renderWithProviders(<EmailDigestPage />, { initialEntries: ['/email-digest?kid=Nobody'] });
    await waitFor(() => {
      expect(screen.getByText('for Thanushan')).toBeInTheDocument();
    });
  });

  it('renders a kid switcher chip row when the parent has 2+ integrations', async () => {
    mockListIntegrations.mockResolvedValue({ data: twoKids });
    renderWithProviders(<EmailDigestPage />, { initialEntries: ['/email-digest?kid=Thanushan'] });
    await waitFor(() => {
      expect(screen.getByRole('tab', { name: 'Thanushan' })).toBeInTheDocument();
    });
    expect(screen.getByRole('tab', { name: 'Haashini' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Thanushan' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: 'Haashini' })).toHaveAttribute('aria-selected', 'false');
  });

  it('switches active child when a kid chip is clicked', async () => {
    mockListIntegrations.mockResolvedValue({ data: twoKids });
    renderWithProviders(<EmailDigestPage />, { initialEntries: ['/email-digest?kid=Thanushan'] });
    await waitFor(() => {
      expect(screen.getByText('for Thanushan')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('tab', { name: 'Haashini' }));

    await waitFor(() => {
      expect(screen.getByText('for Haashini')).toBeInTheDocument();
    });
  });

  it('does NOT render the switcher when the parent has only one integration', async () => {
    mockListIntegrations.mockResolvedValue({ data: [twoKids[0]] });
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByText('for Thanushan')).toBeInTheDocument();
    });
    expect(screen.queryByRole('tab', { name: 'Thanushan' })).not.toBeInTheDocument();
  });
});

// #4044: unified Email Digest page must render ALL of the parent's kids in
// "Your kids" — including kids without a ParentChildProfile row. Adding a
// school email to a kid that has no profile yet must auto-create the profile
// first, then add the email.
describe('EmailDigestPage — unified renders all kids (#4044)', () => {
  beforeEach(() => {
    flagEnabledMock.mockReturnValue(true);
    mockListIntegrations.mockResolvedValue({ data: [buildIntegration()] });
    mockListMonitoredSenders.mockResolvedValue({ data: [] });
  });

  it('renders all parent kids even when only some have profiles', async () => {
    // Two kids on the parent's account. Only the first has a profile.
    mockGetChildren.mockResolvedValue([
      buildKid({ student_id: 9001, user_id: 500, full_name: 'Thanushan Last' }),
      buildKid({ student_id: 9002, user_id: 501, full_name: 'Haashini Last' }),
    ]);
    mockListChildProfiles.mockResolvedValue({
      data: [
        buildChildProfile({
          id: 11,
          student_id: 500,
          first_name: 'Thanushan',
        }),
      ],
    });

    renderWithProviders(<EmailDigestPage />);

    await waitFor(() => {
      expect(screen.getByText('Your kids')).toBeInTheDocument();
    });
    // Both kids show up.
    expect(screen.getByText('Thanushan')).toBeInTheDocument();
    expect(screen.getByText('Haashini')).toBeInTheDocument();
    // The kid without a profile shows the "+ Add school email" CTA (note:
    // 'Add school email' rather than 'Add another school email' because they
    // have zero school emails configured).
    expect(
      screen.getAllByRole('button', { name: '+ Add school email' }).length,
    ).toBeGreaterThanOrEqual(1);
  });

  it('renders a placeholder row for a kid with no profile (and no Profile fetch row)', async () => {
    mockGetChildren.mockResolvedValue([
      buildKid({ student_id: 9002, user_id: 501, full_name: 'Haashini Last' }),
    ]);
    mockListChildProfiles.mockResolvedValue({ data: [] });

    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByText('Haashini')).toBeInTheDocument();
    });
    expect(screen.getByText('No school email configured yet.')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: '+ Add school email' }),
    ).toBeInTheDocument();
  });

  it('auto-creates a profile then adds the school email when the kid has no profile', async () => {
    mockGetChildren.mockResolvedValue([
      buildKid({ student_id: 9002, user_id: 501, full_name: 'Haashini Last' }),
    ]);
    mockListChildProfiles.mockResolvedValue({ data: [] });
    mockCreateChildProfile.mockResolvedValue({
      data: buildChildProfile({ id: 99, student_id: 501, first_name: 'Haashini' }),
    });
    mockAddChildSchoolEmail.mockResolvedValue({
      data: {
        id: 1,
        child_profile_id: 99,
        email_address: 'haashini@ocdsb.ca',
        forwarding_seen_at: null,
        created_at: '2026-04-23T00:00:00Z',
      },
    });

    renderWithProviders(<EmailDigestPage />);

    // Wait for the kid row to render.
    await waitFor(() => {
      expect(screen.getByText('Haashini')).toBeInTheDocument();
    });

    // Click "+ Add school email" to open the inline editor.
    fireEvent.click(screen.getByRole('button', { name: '+ Add school email' }));

    // Type a valid school email and submit.
    const input = await screen.findByPlaceholderText('kid@ocdsb.ca');
    fireEvent.change(input, { target: { value: 'haashini@ocdsb.ca' } });

    fireEvent.click(screen.getByRole('button', { name: 'Add' }));

    // createChildProfile must be called first with the kid's first_name +
    // student_id, then addChildSchoolEmail with the returned profile id.
    await waitFor(() => {
      expect(mockCreateChildProfile).toHaveBeenCalled();
    });
    const [[createPayload]] = mockCreateChildProfile.mock.calls;
    expect(createPayload).toMatchObject({
      first_name: 'Haashini',
      student_id: 501,
    });

    await waitFor(() => {
      expect(mockAddChildSchoolEmail).toHaveBeenCalled();
    });
    const [[profileId, email]] = mockAddChildSchoolEmail.mock.calls;
    expect(profileId).toBe(99);
    expect(email).toBe('haashini@ocdsb.ca');
  });

  it('does NOT call createChildProfile when adding an email for a kid that already has a profile', async () => {
    mockGetChildren.mockResolvedValue([
      buildKid({ student_id: 9001, user_id: 500, full_name: 'Thanushan Last' }),
    ]);
    mockListChildProfiles.mockResolvedValue({
      data: [
        buildChildProfile({
          id: 11,
          student_id: 500,
          first_name: 'Thanushan',
        }),
      ],
    });
    mockAddChildSchoolEmail.mockResolvedValue({
      data: {
        id: 1,
        child_profile_id: 11,
        email_address: 'thanushan@ocdsb.ca',
        forwarding_seen_at: null,
        created_at: '2026-04-23T00:00:00Z',
      },
    });

    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByText('Thanushan')).toBeInTheDocument();
    });

    fireEvent.click(
      screen.getByRole('button', { name: '+ Add school email' }),
    );
    const input = await screen.findByPlaceholderText('kid@ocdsb.ca');
    fireEvent.change(input, { target: { value: 'thanushan@ocdsb.ca' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add' }));

    await waitFor(() => {
      expect(mockAddChildSchoolEmail).toHaveBeenCalled();
    });
    expect(mockCreateChildProfile).not.toHaveBeenCalled();
    const [[profileId, email]] = mockAddChildSchoolEmail.mock.calls;
    expect(profileId).toBe(11);
    expect(email).toBe('thanushan@ocdsb.ca');
  });

  it('merges legacy NULL-student_id profile into the linked kid row by name (#4101)', async () => {
    // Legacy wizard-created profile: student_id is null, first_name matches
    // the linked kid. The kid must render exactly once with the legacy
    // profile's school emails — no duplicate placeholder row.
    mockGetChildren.mockResolvedValue([
      buildKid({ student_id: 9001, user_id: 500, full_name: 'Haashini Last' }),
    ]);
    mockListChildProfiles.mockResolvedValue({
      data: [
        buildChildProfile({
          id: 11,
          student_id: null, // legacy NULL — Stream 1 backfill missed this row
          first_name: 'Haashini',
          school_emails: [
            {
              id: 700,
              child_profile_id: 11,
              email_address: 'haashini@ocdsb.ca',
              forwarding_seen_at: null,
              created_at: '2026-04-01T00:00:00Z',
            },
          ],
        }),
      ],
    });

    renderWithProviders(<EmailDigestPage />);

    await waitFor(() => {
      expect(screen.getByText('Haashini')).toBeInTheDocument();
    });

    // Exactly one Haashini row.
    expect(screen.getAllByText('Haashini')).toHaveLength(1);

    // Existing school email is visible (matched via first_name fallback).
    expect(screen.getByText('haashini@ocdsb.ca')).toBeInTheDocument();

    // The × remove button is present (so it's a profile row, not a placeholder).
    expect(
      screen.getByRole('button', { name: 'Remove haashini@ocdsb.ca' }),
    ).toBeInTheDocument();
  });

  it('renders an orphan profile (no matching parent kid) so legacy data is visible', async () => {
    // #4100 pass-1 review suggestion 7: a profile whose student_id doesn't
    // match any kid on the parent's account (e.g., kid was unlinked but the
    // profile lingered) must still render so school-email management isn't
    // hidden.
    mockGetChildren.mockResolvedValue([]);
    mockListChildProfiles.mockResolvedValue({
      data: [
        buildChildProfile({
          id: 77,
          student_id: 99999, // not in mockGetChildren
          first_name: 'OrphanKid',
        }),
      ],
    });

    renderWithProviders(<EmailDigestPage />);

    await waitFor(() => {
      expect(screen.getByText('OrphanKid')).toBeInTheDocument();
    });
    expect(
      screen.getByRole('button', { name: '+ Add school email' }),
    ).toBeInTheDocument();
  });
});

// #4098: parents must be able to remove school-email rows from the unified
// digest page (legacy setup wizard sometimes seeded misclassified entries).
describe('EmailDigestPage — unified remove school email (#4098)', () => {
  beforeEach(() => {
    flagEnabledMock.mockReturnValue(true);
    mockListIntegrations.mockResolvedValue({ data: [buildIntegration()] });
    mockListMonitoredSenders.mockResolvedValue({ data: [] });
    // No parent kids list set; the profile below renders as an "orphan"
    // row (kind === 'profile') so the × button still renders per #4098.
    mockGetChildren.mockResolvedValue([]);
    mockListChildProfiles.mockResolvedValue({
      data: [
        buildChildProfile({
          id: 11,
          first_name: 'Thanushan',
          school_emails: [
            {
              id: 501,
              child_profile_id: 11,
              email_address: 'no-reply@classroom.google.com',
              forwarding_seen_at: null,
              created_at: '2026-04-01T00:00:00Z',
            },
            {
              id: 502,
              child_profile_id: 11,
              email_address: 'kid@ocdsb.ca',
              forwarding_seen_at: null,
              created_at: '2026-04-01T00:00:00Z',
            },
          ],
        }),
      ],
    });
  });

  it('renders a remove button for each school-email row', async () => {
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByText('no-reply@classroom.google.com')).toBeInTheDocument();
    });
    expect(
      screen.getByRole('button', { name: 'Remove no-reply@classroom.google.com' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Remove kid@ocdsb.ca' }),
    ).toBeInTheDocument();
  });

  it('calls removeChildSchoolEmail with (profileId, emailId) when confirmed', async () => {
    confirmResolveValue = true;
    mockRemoveChildSchoolEmail.mockResolvedValue({ data: {} });
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: 'Remove no-reply@classroom.google.com' }),
      ).toBeInTheDocument();
    });

    fireEvent.click(
      screen.getByRole('button', { name: 'Remove no-reply@classroom.google.com' }),
    );

    await waitFor(() => {
      expect(mockRemoveChildSchoolEmail).toHaveBeenCalledWith(11, 501);
    });
  });

  it('does NOT call API when the confirm modal is cancelled', async () => {
    confirmResolveValue = false;
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: 'Remove kid@ocdsb.ca' }),
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Remove kid@ocdsb.ca' }));

    // Allow the confirm promise + microtasks to resolve.
    await waitFor(() => {
      expect(mockRemoveChildSchoolEmail).not.toHaveBeenCalled();
    });
  });

  it('shows an error banner when the remove API fails', async () => {
    confirmResolveValue = true;
    mockRemoveChildSchoolEmail.mockRejectedValue({
      response: { data: { detail: 'School email is in use.' } },
    });
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: 'Remove kid@ocdsb.ca' }),
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Remove kid@ocdsb.ca' }));

    await waitFor(() => {
      expect(screen.getByText('School email is in use.')).toBeInTheDocument();
    });
  });
});

describe('EmailDigestPage — unified Sync + Send Digest (#4056)', () => {
  beforeEach(() => {
    flagEnabledMock.mockReturnValue(true);
    mockListIntegrations.mockResolvedValue({ data: [buildIntegration()] });
    mockTriggerSync.mockResolvedValue({ data: buildIntegration() });
    // #4483: unified view now calls the parent-scoped endpoint.
    mockSendDigestNowForParent.mockResolvedValue({
      data: { status: 'delivered', email_count: 3, message: 'Digest sent!' },
    });
    mockSendDigestNow.mockResolvedValue({
      data: { status: 'delivered', email_count: 3, message: 'Digest sent!' },
    });
  });

  it('renders the Sync Now button when activeIntegration is active', async () => {
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Sync Now' })).toBeInTheDocument();
    });
  });

  it('clicking Sync Now calls triggerSync(integrationId)', async () => {
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Sync Now' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Sync Now' }));

    await waitFor(() => {
      expect(mockTriggerSync).toHaveBeenCalledWith(1);
    });
  });

  it('renders the Send Digest Now button', async () => {
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Send Digest Now' })).toBeInTheDocument();
    });
  });

  // #4483 (D2/D3): unified UI now calls the parent-scoped endpoint so the
  // V2 worker handles multi-kid framing in subject + body. Per-integration
  // sendDigestNow must NOT be called from the unified view.
  it('clicking Send Digest Now calls sendDigestNowForParent (parent-scoped, #4483)', async () => {
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Send Digest Now' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Send Digest Now' }));

    await waitFor(() => {
      expect(mockSendDigestNowForParent).toHaveBeenCalled();
    });
    // Crucially: the per-integration endpoint must NOT be called.
    expect(mockSendDigestNow).not.toHaveBeenCalled();
  });

  it('renders the per-channel status banner with delivered status (no retry button)', async () => {
    // #4483: payload comes from sendDigestNowForParent in the unified view.
    mockSendDigestNowForParent.mockResolvedValue({
      data: { status: 'delivered', email_count: 5, message: 'Digest sent to 5 messages.' },
    });
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Send Digest Now' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Send Digest Now' }));

    await waitFor(() => {
      const banner = screen.getByText('Digest sent to 5 messages.').closest('.ed-digest-status');
      expect(banner).toBeInTheDocument();
      expect(banner).toHaveAttribute('data-status', 'delivered');
    });
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument();
  });

  it('renders the per-channel status banner with failed status (shows Try again button)', async () => {
    mockSendDigestNowForParent.mockResolvedValue({
      data: { status: 'failed', email_count: 0, message: 'Failed to deliver digest.' },
    });
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Send Digest Now' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Send Digest Now' }));

    await waitFor(() => {
      const banner = screen.getByText('Failed to deliver digest.').closest('.ed-digest-status');
      expect(banner).toBeInTheDocument();
      expect(banner).toHaveAttribute('data-status', 'failed');
    });
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument();
  });

  // #4102 pass-1 review: cover the remaining status branches the legacy
  // tests had but the unified port skipped.
  it('renders amber partial status with failed-channel list', async () => {
    mockSendDigestNowForParent.mockResolvedValue({
      data: {
        status: 'partial',
        email_count: 2,
        message: 'Digest partially delivered (2 emails). Failed channels: WhatsApp.',
        channel_status: { in_app: true, email: true, whatsapp: false },
      },
    });
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Send Digest Now' })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send Digest Now' }));
    await waitFor(() => {
      expect(screen.getByText(/partially delivered/)).toBeInTheDocument();
    });
    const banner = screen.getByText(/partially delivered/).closest('.ed-digest-status') as HTMLElement;
    expect(banner).toHaveAttribute('data-status', 'partial');
    expect(banner.textContent).toContain('WhatsApp');
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument();
  });

  it('renders skipped status WITH preferences link when reason=no_eligible_channels', async () => {
    mockSendDigestNowForParent.mockResolvedValue({
      data: {
        status: 'skipped',
        email_count: 0,
        message: 'No eligible delivery channels. Configure your delivery preferences.',
        reason: 'no_eligible_channels',
      },
    });
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Send Digest Now' })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send Digest Now' }));
    await waitFor(() => {
      expect(screen.getByText(/No eligible delivery channels/)).toBeInTheDocument();
    });
    expect(screen.getByRole('link', { name: 'Open preferences' })).toBeInTheDocument();
  });

  it('does NOT render preferences link for skipped with reason=no_new_emails', async () => {
    mockSendDigestNowForParent.mockResolvedValue({
      data: {
        status: 'skipped',
        email_count: 0,
        message: 'No new emails',
        reason: 'no_new_emails',
      },
    });
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Send Digest Now' })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send Digest Now' }));
    await waitFor(() => {
      expect(screen.getByText('No new emails')).toBeInTheDocument();
    });
    expect(screen.queryByRole('link', { name: 'Open preferences' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument();
  });
});

// #4483 (D2/D3): single-integration legacy view (flag OFF) still calls the
// per-integration `sendDigestNow` endpoint — smaller blast radius for users
// not yet on the V2 ramp. Guards against accidental cross-pollination from
// the unified-view changes.
describe('EmailDigestPage — legacy view still uses per-integration sendDigestNow (#4483)', () => {
  beforeEach(() => {
    flagEnabledMock.mockReturnValue(false);
    mockListIntegrations.mockResolvedValue({ data: [buildIntegration()] });
    mockTriggerSync.mockResolvedValue({ data: buildIntegration() });
    mockSendDigestNow.mockResolvedValue({
      data: { status: 'delivered', email_count: 1, message: 'Digest sent!' },
    });
    mockSendDigestNowForParent.mockResolvedValue({
      data: { status: 'delivered', email_count: 1, message: 'should not be called' },
    });
  });

  it('clicking Send Digest Now in legacy view calls per-integration sendDigestNow, not the parent-scoped endpoint', async () => {
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Send Digest Now' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Send Digest Now' }));

    await waitFor(() => {
      expect(mockSendDigestNow).toHaveBeenCalledWith(1);
    });
    expect(mockSendDigestNowForParent).not.toHaveBeenCalled();
  });
});

// #4349 Stream E: digest-history rendering is now owned by DigestHistoryPanel.
// Behavior tests (loading / empty / expand / sanitize) live in
// DigestHistoryPanel.test.tsx. Here we only assert the page wires the panel
// up at all + passes the expected `limit` for the dedicated /email-digest
// page (which historically fetched 50 entries).
describe('EmailDigestPage — unified Digest History (#4056, #4349 Stream E)', () => {
  beforeEach(() => {
    flagEnabledMock.mockReturnValue(true);
    mockListIntegrations.mockResolvedValue({ data: [buildIntegration()] });
    mockListChildProfiles.mockResolvedValue({ data: [] });
    mockListMonitoredSenders.mockResolvedValue({ data: [] });
  });

  it('renders the shared DigestHistoryPanel with limit=50 and the original empty-state copy', async () => {
    renderWithProviders(<EmailDigestPage />);

    const panel = await screen.findByTestId('digest-history-panel');
    expect(panel).toBeInTheDocument();
    expect(panel).toHaveAttribute('data-limit', '50');
    expect(panel).toHaveAttribute(
      'data-empty-state',
      'No digests delivered yet. Your first digest will appear here after the next scheduled run.',
    );
  });
});

// ---------------------------------------------------------------------------
// #4329 — Discovered school addresses (banner + assign modal)
// ---------------------------------------------------------------------------

describe('EmailDigestPage — discovered school emails (#4329)', () => {
  beforeEach(() => {
    flagEnabledMock.mockReturnValue(true);
    mockListIntegrations.mockResolvedValue({ data: [buildIntegration()] });
    mockListChildProfiles.mockResolvedValue({
      data: [
        buildChildProfile({ id: 11, first_name: 'Haashini' }),
        buildChildProfile({ id: 12, first_name: 'Thanushan' }),
      ],
    });
  });

  it('hides the banner when no discoveries exist', async () => {
    mockListDiscoveredSchoolEmails.mockResolvedValue({ data: [] });
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByText('Your kids')).toBeInTheDocument();
    });
    expect(screen.queryByText(/couldn.t classify/)).not.toBeInTheDocument();
  });

  it('renders the banner when discoveries exist', async () => {
    mockListDiscoveredSchoolEmails.mockResolvedValue({
      data: [
        {
          id: 1,
          email_address: '349017574@gapps.yrdsb.ca',
          sample_sender: 'teacher@yrdsb.ca',
          occurrences: 3,
          first_seen_at: '2026-04-01T00:00:00Z',
          last_seen_at: '2026-04-25T00:00:00Z',
        },
      ],
    });
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByText(/couldn.t classify/)).toBeInTheDocument();
    });
    expect(
      screen.getByRole('button', { name: /Assign to a kid/ }),
    ).toBeInTheDocument();
  });

  it('opens the modal when the banner button is clicked', async () => {
    mockListDiscoveredSchoolEmails.mockResolvedValue({
      data: [
        {
          id: 1,
          email_address: '349017574@gapps.yrdsb.ca',
          sample_sender: null,
          occurrences: 1,
          first_seen_at: '2026-04-01T00:00:00Z',
          last_seen_at: '2026-04-25T00:00:00Z',
        },
      ],
    });
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByText(/couldn.t classify/)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Assign to a kid/ }));

    await waitFor(() => {
      expect(
        screen.getByRole('dialog', { name: /Assign discovered school addresses/ }),
      ).toBeInTheDocument();
    });
    expect(screen.getByText('349017574@gapps.yrdsb.ca')).toBeInTheDocument();
  });

  it('calls assignDiscoveredSchoolEmail when a kid is selected and Assign clicked', async () => {
    mockListDiscoveredSchoolEmails.mockResolvedValue({
      data: [
        {
          id: 42,
          email_address: 'kid@gapps.yrdsb.ca',
          sample_sender: null,
          occurrences: 1,
          first_seen_at: '2026-04-01T00:00:00Z',
          last_seen_at: '2026-04-25T00:00:00Z',
        },
      ],
    });
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByText(/couldn.t classify/)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /Assign to a kid/ }));

    const dialog = await screen.findByRole('dialog', {
      name: /Assign discovered school addresses/,
    });
    const select = within(dialog).getByRole('combobox', {
      name: /Assign kid@gapps.yrdsb.ca to a kid/,
    });
    fireEvent.change(select, { target: { value: '11' } });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Assign' }));

    await waitFor(() => {
      expect(mockAssignDiscoveredSchoolEmail).toHaveBeenCalledWith(42, 11);
    });
  });

  it('calls dismissDiscoveredSchoolEmail when Dismiss clicked', async () => {
    mockListDiscoveredSchoolEmails.mockResolvedValue({
      data: [
        {
          id: 7,
          email_address: 'bye@gapps.yrdsb.ca',
          sample_sender: null,
          occurrences: 1,
          first_seen_at: '2026-04-01T00:00:00Z',
          last_seen_at: '2026-04-25T00:00:00Z',
        },
      ],
    });
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByText(/couldn.t classify/)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /Assign to a kid/ }));

    const dialog = await screen.findByRole('dialog', {
      name: /Assign discovered school addresses/,
    });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Dismiss' }));

    await waitFor(() => {
      expect(mockDismissDiscoveredSchoolEmail).toHaveBeenCalledWith(7);
    });
  });
});

describe('EmailDigestPage — CB-EDIGEST-002 dashboard flag gate (#4594)', () => {
  it('renders the unified UI when email_digest_dashboard_v1 is OFF (and unified flag ON)', async () => {
    flagEnabledMock.mockReturnValue(true); // unified V2 flag ON
    dashboardFlagMock.mockReturnValue(false); // dashboard gate OFF
    mockListIntegrations.mockResolvedValue({ data: [buildIntegration()] });
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      // Unified UI: "Sync & Send" section is unique to EmailDigestPageUnified.
      expect(screen.getByRole('heading', { name: 'Sync & Send' })).toBeInTheDocument();
    });
    expect(screen.queryByTestId('dashboard-view-stub')).not.toBeInTheDocument();
  });

  it('renders the legacy UI when both flags are OFF', async () => {
    flagEnabledMock.mockReturnValue(false); // unified V2 flag OFF
    dashboardFlagMock.mockReturnValue(false); // dashboard gate OFF
    mockListIntegrations.mockResolvedValue({ data: [buildIntegration()] });
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      // Legacy UI shows the WhatsApp section as a top-level card.
      expect(screen.getByText('Receive Digest on WhatsApp')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('dashboard-view-stub')).not.toBeInTheDocument();
  });

  it('renders DashboardView when email_digest_dashboard_v1 is ON', async () => {
    flagEnabledMock.mockReturnValue(true); // unified V2 flag ON
    dashboardFlagMock.mockReturnValue(true); // dashboard gate ON
    mockListIntegrations.mockResolvedValue({ data: [buildIntegration()] });
    renderWithProviders(<EmailDigestPage />);
    await waitFor(() => {
      expect(screen.getByTestId('dashboard-view-stub')).toBeInTheDocument();
    });
    // Legacy/unified UI must NOT also render.
    expect(screen.queryByRole('heading', { name: 'Sync & Send' })).not.toBeInTheDocument();
  });

  it('forces legacy via ?legacy=1 even when dashboard flag is ON', async () => {
    flagEnabledMock.mockReturnValue(true);
    dashboardFlagMock.mockReturnValue(true);
    mockListIntegrations.mockResolvedValue({ data: [buildIntegration()] });
    renderWithProviders(<EmailDigestPage />, { initialEntries: ['/email-digest?legacy=1'] });
    await waitFor(() => {
      expect(screen.getByText('Receive Digest on WhatsApp')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('dashboard-view-stub')).not.toBeInTheDocument();
  });
});
