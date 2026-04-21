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
