import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor, fireEvent } from '@testing-library/react';
import { renderWithProviders } from '../test/helpers';
import { EmailDigestSetupWizard } from './EmailDigestSetupWizard';

const mockListIntegrations = vi.fn();
const mockUpdateIntegration = vi.fn();
const mockAddMonitoredEmail = vi.fn();
const mockUpdateSettings = vi.fn();

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
  };
});

beforeEach(() => {
  vi.clearAllMocks();
  mockUpdateIntegration.mockResolvedValue({ data: {} });
  mockAddMonitoredEmail.mockResolvedValue({ data: {} });
  mockUpdateSettings.mockResolvedValue({ data: {} });
});

describe('EmailDigestSetupWizard — digest format options', () => {
  it('lists sectioned/full/brief/actions_only on Step 3 with sectioned as default', async () => {
    // Land the wizard on Step 2 by seeding an existing integration, then
    // advance to Step 3 so the Digest Format <select> renders.
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
