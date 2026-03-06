import { render, screen, waitFor, act } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';

// Mock the notes API
const mockGetByContent = vi.fn();
const mockUpsert = vi.fn();
const mockGetChildNotes = vi.fn();

vi.mock('../api/notes', () => ({
  notesApi: {
    getByContent: (...args: unknown[]) => mockGetByContent(...args),
    upsert: (...args: unknown[]) => mockUpsert(...args),
    getChildNotes: (...args: unknown[]) => mockGetChildNotes(...args),
  },
}));

import { NotesPanel } from './NotesPanel';

describe('NotesPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: no existing note (404)
    mockGetByContent.mockRejectedValue({ response: { status: 404 } });
    mockUpsert.mockResolvedValue({
      id: 1,
      user_id: 1,
      course_content_id: 42,
      content: '',
      plain_text: null,
      has_images: false,
      highlights_json: '[]',
      created_at: '2026-01-01T00:00:00',
      updated_at: null,
    });
  });

  it('processes addHighlight after loading completes (regression #1212)', async () => {
    const onHighlightConsumed = vi.fn();
    const onHighlightsChange = vi.fn();

    render(
      <NotesPanel
        courseContentId={42}
        isOpen={true}
        onClose={() => {}}
        addHighlight={{ text: 'important concept' }}
        onHighlightConsumed={onHighlightConsumed}
        onHighlightsChange={onHighlightsChange}
      />
    );

    // Wait for loadNote to complete and addHighlight effect to fire
    await waitFor(() => {
      expect(onHighlightConsumed).toHaveBeenCalled();
    });

    // onHighlightsChange should have been called with the new highlight
    const calls = onHighlightsChange.mock.calls;
    const lastCall = calls[calls.length - 1];
    expect(lastCall[0]).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ text: 'important concept' }),
      ])
    );
  });

  it('processes appendText after loading completes (regression #1212)', async () => {
    const onAppendConsumed = vi.fn();

    render(
      <NotesPanel
        courseContentId={42}
        isOpen={true}
        onClose={() => {}}
        appendText="some highlighted text"
        onAppendConsumed={onAppendConsumed}
      />
    );

    await waitFor(() => {
      expect(onAppendConsumed).toHaveBeenCalled();
    });

    // The appended text should appear quoted in the textarea
    const textarea = screen.getByPlaceholderText('Type your notes here...');
    expect((textarea as HTMLTextAreaElement).value).toContain('> some highlighted text');
  });
});
