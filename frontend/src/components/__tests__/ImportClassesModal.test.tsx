import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import ImportClassesModal from '../ImportClassesModal';
import type { PreviewResponse, BulkCreateResponse } from '../../api/classImport';

// Mock focus trap (jsdom + focus logic is noisy)
vi.mock('../../hooks/useFocusTrap', () => ({
  useFocusTrap: () => ({ current: null }),
}));

// Mock API module
vi.mock('../../api/classImport', () => ({
  fetchGoogleClassroomPreview: vi.fn(),
  parseScreenshot: vi.fn(),
  bulkCreateClasses: vi.fn(),
}));

import {
  fetchGoogleClassroomPreview,
  parseScreenshot,
  bulkCreateClasses,
} from '../../api/classImport';

const mockedPreview = fetchGoogleClassroomPreview as unknown as ReturnType<typeof vi.fn>;
const mockedParse = parseScreenshot as unknown as ReturnType<typeof vi.fn>;
const mockedBulk = bulkCreateClasses as unknown as ReturnType<typeof vi.fn>;

function connectedPreview(): PreviewResponse {
  return {
    connected: true,
    courses: [
      {
        class_name: 'Algebra I',
        section: 'Block A',
        teacher_name: 'jane doe',
        teacher_email: 'jane@school.com',
        google_classroom_id: 'gc-1',
        existing: false,
        existing_course_id: null,
      },
      {
        class_name: 'History',
        section: null,
        teacher_name: 'Bob Smith',
        teacher_email: null,
        google_classroom_id: 'gc-2',
        existing: true,
        existing_course_id: 42,
      },
    ],
  };
}

describe('ImportClassesModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('does not render when closed', () => {
    render(<ImportClassesModal open={false} onClose={vi.fn()} onCreated={vi.fn()} />);
    expect(screen.queryByText('Import classes')).not.toBeInTheDocument();
  });

  it('renders both tabs and calls preview on mount (Google tab default)', async () => {
    mockedPreview.mockResolvedValueOnce(connectedPreview());
    render(<ImportClassesModal open={true} onClose={vi.fn()} onCreated={vi.fn()} />);

    expect(screen.getByText('Import classes')).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /From Google Classroom/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /From screenshot/i })).toBeInTheDocument();

    await waitFor(() => expect(mockedPreview).toHaveBeenCalledTimes(1));
    await screen.findByDisplayValue('Algebra I');
  });

  it('switching tabs does not lose Google preview state', async () => {
    mockedPreview.mockResolvedValueOnce(connectedPreview());
    render(<ImportClassesModal open={true} onClose={vi.fn()} onCreated={vi.fn()} />);

    await screen.findByDisplayValue('Algebra I');

    fireEvent.click(screen.getByRole('tab', { name: /From screenshot/i }));
    expect(screen.getByText(/Drag an image here/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: /From Google Classroom/i }));
    expect(screen.getByDisplayValue('Algebra I')).toBeInTheDocument();
    // Preview should not be refetched
    expect(mockedPreview).toHaveBeenCalledTimes(1);
  });

  it('Confirm button disabled when no rows selected and enabled with selections', async () => {
    mockedPreview.mockResolvedValueOnce(connectedPreview());
    render(<ImportClassesModal open={true} onClose={vi.fn()} onCreated={vi.fn()} />);

    // Algebra I is pre-selected (not existing); existing "History" is not selected.
    // Button shows count: "Create 1 class"
    const confirmBtn = await screen.findByRole('button', { name: /Create 1 class/i });
    expect(confirmBtn).toBeEnabled();

    // Uncheck the only selected row
    const checkboxes = screen.getAllByRole('checkbox');
    // First checkbox is for Algebra I (selected)
    fireEvent.click(checkboxes[0]);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Create 0 classes/i })).toBeDisabled();
    });
  });

  it('validation errors gate submit', async () => {
    mockedPreview.mockResolvedValueOnce(connectedPreview());
    render(<ImportClassesModal open={true} onClose={vi.fn()} onCreated={vi.fn()} />);

    const algInput = await screen.findByDisplayValue('Algebra I');
    // Clear the required class_name on the selected row
    fireEvent.change(algInput, { target: { value: '' } });

    await waitFor(() => {
      const btn = screen.getByRole('button', { name: /Create \d+ class/i });
      expect(btn).toBeDisabled();
    });
  });

  it('on successful bulk create, onCreated fires with created count', async () => {
    mockedPreview.mockResolvedValueOnce(connectedPreview());
    const bulkRes: BulkCreateResponse = {
      created: [
        { index: 0, course_id: 101, name: 'Algebra I' },
      ],
      failed: [],
    };
    mockedBulk.mockResolvedValueOnce(bulkRes);

    const onClose = vi.fn();
    const onCreated = vi.fn();
    render(<ImportClassesModal open={true} onClose={onClose} onCreated={onCreated} />);

    const confirmBtn = await screen.findByRole('button', { name: /Create 1 class/i });

    await act(async () => {
      fireEvent.click(confirmBtn);
    });

    // Result summary step appears
    await screen.findByText('Import complete');
    expect(mockedBulk).toHaveBeenCalledTimes(1);

    // Click "Done" to finish
    fireEvent.click(screen.getByRole('button', { name: /Done/i }));

    expect(onCreated).toHaveBeenCalledWith(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('disconnected preview shows Connect CTA but screenshot tab usable', async () => {
    mockedPreview.mockResolvedValueOnce({
      connected: false,
      connect_url: 'https://example.com/connect',
      courses: [],
    });
    render(<ImportClassesModal open={true} onClose={vi.fn()} onCreated={vi.fn()} />);

    const link = await screen.findByRole('link', { name: /Connect Google/i });
    expect(link).toHaveAttribute('href', 'https://example.com/connect');

    // Screenshot tab is still usable
    fireEvent.click(screen.getByRole('tab', { name: /From screenshot/i }));
    expect(screen.getByText(/Drag an image here/i)).toBeInTheDocument();
  });

  it('parseScreenshot failure (422) shows friendly error', async () => {
    mockedPreview.mockResolvedValueOnce({ connected: false, connect_url: '', courses: [] });
    const err: any = new Error('bad');
    err.response = { status: 422 };
    mockedParse.mockRejectedValueOnce(err);

    render(<ImportClassesModal open={true} onClose={vi.fn()} onCreated={vi.fn()} />);

    fireEvent.click(screen.getByRole('tab', { name: /From screenshot/i }));

    // Simulate a file selection via the hidden input
    const file = new File(['dummy'], 'shot.png', { type: 'image/png' });
    // URL.createObjectURL is not in jsdom
    if (!('createObjectURL' in URL)) {
      Object.defineProperty(URL, 'createObjectURL', { writable: true, value: vi.fn(() => 'blob:mock') });
      Object.defineProperty(URL, 'revokeObjectURL', { writable: true, value: vi.fn() });
    } else {
      (URL.createObjectURL as any) = vi.fn(() => 'blob:mock');
      (URL.revokeObjectURL as any) = vi.fn();
    }

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    Object.defineProperty(input, 'files', { value: [file] });
    fireEvent.change(input);

    const parseBtn = await screen.findByRole('button', { name: /Parse screenshot/i });
    await act(async () => {
      fireEvent.click(parseBtn);
    });

    await screen.findByText(/couldn't read that screenshot/i);
  });

  it('rejects non-whitelisted image types with a friendly error', async () => {
    mockedPreview.mockResolvedValueOnce({ connected: false, connect_url: '', courses: [] });
    render(<ImportClassesModal open={true} onClose={vi.fn()} onCreated={vi.fn()} />);
    fireEvent.click(screen.getByRole('tab', { name: /From screenshot/i }));
    // gif should be rejected
    const file = new File(['gif'], 'animated.gif', { type: 'image/gif' });
    // URL.createObjectURL shim (match existing shim pattern in the file)
    if (!('createObjectURL' in URL)) {
      Object.defineProperty(URL, 'createObjectURL', { writable: true, value: vi.fn(() => 'blob:mock') });
      Object.defineProperty(URL, 'revokeObjectURL', { writable: true, value: vi.fn() });
    }
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    Object.defineProperty(input, 'files', { value: [file] });
    fireEvent.change(input);
    await screen.findByText(/Unsupported image type/i);
  });

  it('shows friendly error copy when preview returns 500', async () => {
    const err: any = new Error('Request failed');
    err.response = { status: 500 };
    mockedPreview.mockRejectedValueOnce(err);
    render(<ImportClassesModal open={true} onClose={vi.fn()} onCreated={vi.fn()} />);
    await screen.findByText(/Service temporarily unavailable/i);
  });

  it('shows Anthropic privacy disclosure on the screenshot tab', async () => {
    mockedPreview.mockResolvedValueOnce({ connected: false, connect_url: '', courses: [] });
    render(<ImportClassesModal open={true} onClose={vi.fn()} onCreated={vi.fn()} />);
    fireEvent.click(screen.getByRole('tab', { name: /From screenshot/i }));
    expect(screen.getByText(/processed by Anthropic Claude/i)).toBeInTheDocument();
  });
});
