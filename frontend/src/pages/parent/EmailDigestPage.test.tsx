import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor, fireEvent } from '@testing-library/react';
import { renderWithProviders } from '../../test/helpers';
import { EmailDigestPage } from './EmailDigestPage';
import type { EmailDigestIntegration } from '../../api/parentEmailDigest';

const mockListIntegrations = vi.fn();
const mockGetSettings = vi.fn();
const mockGetLogs = vi.fn();
const mockListMonitoredEmails = vi.fn();
const mockSendWhatsAppOTP = vi.fn();
const mockVerifyWhatsAppOTP = vi.fn();
const mockDisconnectWhatsApp = vi.fn();
const mockSendDigestNow = vi.fn();

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
  };
});

vi.mock('../../components/DashboardLayout', () => ({
  DashboardLayout: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="layout">{children}</div>
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

beforeEach(() => {
  vi.clearAllMocks();
  confirmResolveValue = true;
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
