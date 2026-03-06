import { useEffect, useCallback, useRef, type RefObject } from 'react';

export interface HighlightEntry {
  text: string;
}

const HIGHLIGHT_ATTR = 'data-highlight';
const HIGHLIGHT_ID_ATTR = 'data-highlight-id';
const HIGHLIGHT_CLASS = 'persistent-highlight';

/**
 * Normalize whitespace: collapse runs of whitespace (including newlines) to a single space and trim.
 */
function normalizeWhitespace(str: string): string {
  return str.replace(/\s+/g, ' ').trim();
}

/**
 * Unwrap all existing highlight <mark> elements inside a container,
 * replacing each with its child text nodes.
 */
function clearHighlights(container: HTMLElement): void {
  const marks = container.querySelectorAll(`mark[${HIGHLIGHT_ATTR}]`);
  marks.forEach((mark) => {
    const parent = mark.parentNode;
    if (!parent) return;
    while (mark.firstChild) {
      parent.insertBefore(mark.firstChild, mark);
    }
    parent.removeChild(mark);
    // Merge adjacent text nodes that were split
    parent.normalize();
  });
}

/**
 * Collect all text nodes under a container using TreeWalker.
 */
function getTextNodes(container: HTMLElement): Text[] {
  const nodes: Text[] = [];
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  let node: Text | null;
  while ((node = walker.nextNode() as Text | null)) {
    nodes.push(node);
  }
  return nodes;
}

/**
 * Build a mapping from cumulative character offset to text node,
 * using normalized (whitespace-collapsed) text for matching.
 */
function buildTextMap(textNodes: Text[]): {
  fullText: string;
  segments: Array<{ node: Text; start: number; end: number; text: string }>;
} {
  let offset = 0;
  const segments: Array<{ node: Text; start: number; end: number; text: string }> = [];
  const parts: string[] = [];

  for (const node of textNodes) {
    const raw = node.textContent || '';
    // Collapse internal whitespace but preserve leading/trailing so positions map correctly
    const normalized = raw.replace(/\s+/g, ' ');
    parts.push(normalized);
    segments.push({
      node,
      start: offset,
      end: offset + normalized.length,
      text: normalized,
    });
    offset += normalized.length;
  }

  return { fullText: parts.join(''), segments };
}

/**
 * Create a <mark> element for highlighting.
 */
function createMark(
  highlightId: string,
  onClick?: (text: string) => void,
  fullText?: string,
): HTMLElement {
  const mark = document.createElement('mark');
  mark.setAttribute(HIGHLIGHT_ATTR, '');
  mark.setAttribute(HIGHLIGHT_ID_ATTR, highlightId);
  mark.className = HIGHLIGHT_CLASS;
  if (onClick && fullText) {
    mark.addEventListener('click', () => onClick(fullText));
  }
  return mark;
}

/**
 * Wrap a range within a single text node in a <mark> element.
 */
function wrapRange(
  textNode: Text,
  startInNode: number,
  endInNode: number,
  highlightId: string,
  onClick?: (text: string) => void,
  fullText?: string,
): void {
  const mark = createMark(highlightId, onClick, fullText);

  // Split: [before][match][after]
  if (startInNode > 0) {
    textNode = textNode.splitText(startInNode) as Text;
    endInNode -= startInNode;
  }
  if (endInNode < (textNode.textContent?.length || 0)) {
    textNode.splitText(endInNode);
  }

  // Wrap the matched text node
  const parent = textNode.parentNode;
  if (parent) {
    parent.insertBefore(mark, textNode);
    mark.appendChild(textNode);
  }
}

/**
 * Apply a single highlight across potentially multiple text nodes.
 */
function applyHighlight(
  container: HTMLElement,
  highlight: HighlightEntry,
  highlightId: string,
  onClick?: (text: string) => void,
): boolean {
  const textNodes = getTextNodes(container);
  if (textNodes.length === 0) return false;

  const { fullText, segments } = buildTextMap(textNodes);
  const normalizedSearch = normalizeWhitespace(highlight.text);

  if (!normalizedSearch) return false;

  // Find first occurrence in the full (normalized) text
  const normalizedFull = normalizeWhitespace(fullText);
  const matchIndex = normalizedFull.indexOf(normalizedSearch);
  if (matchIndex === -1) return false;

  // Map the match range back to the unnormalized fullText
  const directIndex = fullText.indexOf(normalizedSearch);
  const useIndex = directIndex !== -1 ? directIndex : matchIndex;
  const useEnd = useIndex + normalizedSearch.length;

  // Find which segments overlap with [useIndex, useEnd)
  const overlapping = segments.filter(
    (seg) => seg.start < useEnd && seg.end > useIndex,
  );

  if (overlapping.length === 0) return false;

  // Process segments in reverse order to avoid invalidating offsets
  for (let i = overlapping.length - 1; i >= 0; i--) {
    const seg = overlapping[i];
    const startInNode = Math.max(0, useIndex - seg.start);
    const endInNode = Math.min(seg.text.length, useEnd - seg.start);

    if (startInNode >= endInNode) continue;

    wrapRange(seg.node, startInNode, endInNode, highlightId, onClick, highlight.text);
  }

  return true;
}

/**
 * Renders persistent yellow highlights within a container element.
 * Uses DOM TreeWalker to find text nodes matching highlight entries,
 * then wraps them in <mark> elements.
 */
export function useHighlightRenderer(
  containerRef: RefObject<HTMLElement | null>,
  highlights: HighlightEntry[],
  onHighlightClick?: (text: string) => void,
) {
  const highlightsRef = useRef(highlights);
  const onClickRef = useRef(onHighlightClick);

  useEffect(() => {
    highlightsRef.current = highlights;
    onClickRef.current = onHighlightClick;
  });

  const applyAllHighlights = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;

    const currentHighlights = highlightsRef.current;
    if (!currentHighlights || currentHighlights.length === 0) {
      clearHighlights(container);
      return;
    }

    clearHighlights(container);

    const textContent = container.textContent || '';
    if (textContent.trim().length === 0) return;

    for (let i = 0; i < currentHighlights.length; i++) {
      const highlight = currentHighlights[i];
      const highlightId = `hl-${i}`;
      const clickHandler = onClickRef.current
        ? (text: string) => onClickRef.current?.(text)
        : undefined;

      applyHighlight(container, highlight, highlightId, clickHandler);
    }
  }, [containerRef]);

  const refreshHighlights = useCallback(() => {
    requestAnimationFrame(() => {
      applyAllHighlights();
    });
  }, [applyAllHighlights]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const applyWhenReady = () => {
      const textContent = container.textContent || '';
      if (textContent.trim().length > 0 && highlights.length > 0) {
        applyAllHighlights();
      }
    };

    requestAnimationFrame(applyWhenReady);

    // Use MutationObserver to detect when content appears (e.g., after Suspense resolves)
    const observer = new MutationObserver(() => {
      requestAnimationFrame(() => {
        applyAllHighlights();
      });
    });

    observer.observe(container, {
      childList: true,
      subtree: true,
      characterData: true,
    });

    return () => {
      observer.disconnect();
      if (container) {
        clearHighlights(container);
      }
    };
  }, [containerRef, highlights, applyAllHighlights]);

  return { refreshHighlights };
}
