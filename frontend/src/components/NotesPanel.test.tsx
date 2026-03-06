import { render, screen, waitFor } from '@testing-library/react';
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

const defaultNote = {
  id: 1,
  user_id: 1,
  course_content_id: 42,
  content: '',
  plain_text: null,
  has_images: false,
  highlights_json: '[]',
  created_at: '2026-01-01T00:00:00',
  updated_at: null,
};

describe('NotesPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: no existing note (404)
    mockGetByContent.mockRejectedValue({ response: { status: 404 } });
    mockGetChildNotes.mockResolvedValue(null);
    mockUpsert.mockResolvedValue(defaultNote);
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

    await waitFor(() => {
      expect(onHighlightConsumed).toHaveBeenCalled();
    });

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

    const textarea = screen.getByPlaceholderText('Type your notes here...');
    expect((textarea as HTMLTextAreaElement).value).toContain('> some highlighted text');
  });

  it('does not overwrite highlights when switching to child notes view (regression #1212)', async () => {
    const onHighlightConsumed = vi.fn();
    const onHighlightsChange = vi.fn();

    // Phase 1: Mount as non-readOnly (resolvedStudent not yet loaded)
    const { rerender } = render(
      <NotesPanel
        courseContentId={42}
        isOpen={true}
        onClose={() => {}}
        addHighlight={{ text: 'my highlight' }}
        onHighlightConsumed={onHighlightConsumed}
        onHighlightsChange={onHighlightsChange}
      />
    );

    // Wait for initial load + highlight processing
    await waitFor(() => {
      expect(onHighlightConsumed).toHaveBeenCalled();
    });

    // Verify highlight was added
    const callsAfterAdd = onHighlightsChange.mock.calls;
    const lastAddCall = callsAfterAdd[callsAfterAdd.length - 1];
    expect(lastAddCall[0]).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ text: 'my highlight' }),
      ])
    );

    // Record call count before rerender
    const callCountBefore = onHighlightsChange.mock.calls.length;

    // Phase 2: resolvedStudent loads → readOnly=true, childStudentId set
    // Child has no notes (returns null)
    mockGetChildNotes.mockResolvedValue(null);

    rerender(
      <NotesPanel
        courseContentId={42}
        isOpen={true}
        onClose={() => {}}
        addHighlight={null}
        onHighlightConsumed={onHighlightConsumed}
        onHighlightsChange={onHighlightsChange}
        readOnly={true}
        childStudentId={99}
        childName="Test Child"
      />
    );

    // Wait for child notes load to complete
    await waitFor(() => {
      expect(mockGetChildNotes).toHaveBeenCalledWith(99, 42);
    });

    // onHighlightsChange should NOT have been called again with []
    // (child view must not overwrite parent highlights)
    const callsAfterRerender = onHighlightsChange.mock.calls.slice(callCountBefore);
    const wipeCall = callsAfterRerender.find(
      (call: unknown[]) => Array.isArray(call[0]) && call[0].length === 0
    );
    expect(wipeCall).toBeUndefined();
  });
});
