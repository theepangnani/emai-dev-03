import { useState, useEffect, useCallback, useRef, type RefObject } from 'react';

export interface TextSelectionState {
  text: string;
  rect: DOMRect;
}

/**
 * Track text selection within a container element.
 * Returns the selected text and its bounding rect, or null if nothing selected.
 */
export function useTextSelection(containerRef: RefObject<HTMLElement | null>) {
  const [selection, setSelection] = useState<TextSelectionState | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearSelection = useCallback(() => setSelection(null), []);

  useEffect(() => {
    const handleSelectionChange = () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        const sel = window.getSelection();
        if (!sel || sel.isCollapsed || !sel.rangeCount) {
          setSelection(null);
          return;
        }

        const text = sel.toString().trim();
        if (text.length < 3) {
          setSelection(null);
          return;
        }

        // Verify selection is within the container
        const container = containerRef.current;
        if (!container) {
          setSelection(null);
          return;
        }

        const range = sel.getRangeAt(0);
        if (!container.contains(range.commonAncestorContainer)) {
          setSelection(null);
          return;
        }

        const rect = range.getBoundingClientRect();
        setSelection({ text, rect });
      }, 150);
    };

    document.addEventListener('selectionchange', handleSelectionChange);
    return () => {
      document.removeEventListener('selectionchange', handleSelectionChange);
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [containerRef]);

  return { selection, clearSelection };
}
