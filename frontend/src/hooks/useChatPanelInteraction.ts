import { useState, useRef, useCallback, useEffect } from 'react';

const MIN_WIDTH = 320;
const MIN_HEIGHT = 380;
const DEFAULT_WIDTH = 400;
const DEFAULT_HEIGHT = 520;
const STORAGE_KEY = 'classbridge-chat-panel-state';

interface PanelState {
  width: number;
  height: number;
  x: number | null;
  y: number | null;
}

function loadState(): PanelState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      return {
        width: Math.max(MIN_WIDTH, parsed.width ?? DEFAULT_WIDTH),
        height: Math.max(MIN_HEIGHT, parsed.height ?? DEFAULT_HEIGHT),
        x: parsed.x ?? null,
        y: parsed.y ?? null,
      };
    }
  } catch { /* ignore */ }
  return { width: DEFAULT_WIDTH, height: DEFAULT_HEIGHT, x: null, y: null };
}

function saveState(state: PanelState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch { /* ignore */ }
}

function isMobile() {
  return window.innerWidth < 768;
}

export function useChatPanelInteraction() {
  const [maximized, setMaximized] = useState(false);
  const [panelState, setPanelState] = useState<PanelState>(loadState);
  const panelRef = useRef<HTMLDivElement>(null);
  const isDragging = useRef(false);
  const isResizing = useRef(false);
  const dragStart = useRef({ mouseX: 0, mouseY: 0, panelX: 0, panelY: 0 });
  const resizeStart = useRef({ mouseX: 0, mouseY: 0, w: 0, h: 0 });

  // Persist state changes
  useEffect(() => {
    if (!maximized) saveState(panelState);
  }, [panelState, maximized]);

  // Clamp position to viewport
  const clampPosition = useCallback((x: number, y: number, w: number, h: number) => {
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    return {
      x: Math.max(0, Math.min(x, vw - w)),
      y: Math.max(0, Math.min(y, vh - h)),
    };
  }, []);

  // --- Drag ---
  const onDragStart = useCallback((e: React.MouseEvent) => {
    if (maximized || isMobile()) return;
    // Don't drag if clicking buttons
    if ((e.target as HTMLElement).closest('button')) return;
    e.preventDefault();
    isDragging.current = true;

    const panel = panelRef.current;
    if (!panel) return;
    const rect = panel.getBoundingClientRect();
    // If no custom position yet, initialize from current panel position
    const currentX = panelState.x ?? rect.left;
    const currentY = panelState.y ?? rect.top;
    dragStart.current = { mouseX: e.clientX, mouseY: e.clientY, panelX: currentX, panelY: currentY };
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'grabbing';
  }, [maximized, panelState.x, panelState.y]);

  const onDragMove = useCallback((e: MouseEvent) => {
    if (!isDragging.current) return;
    const dx = e.clientX - dragStart.current.mouseX;
    const dy = e.clientY - dragStart.current.mouseY;
    const newX = dragStart.current.panelX + dx;
    const newY = dragStart.current.panelY + dy;
    const clamped = clampPosition(newX, newY, panelState.width, panelState.height);
    setPanelState(prev => ({ ...prev, x: clamped.x, y: clamped.y }));
  }, [clampPosition, panelState.width, panelState.height]);

  const onDragEnd = useCallback(() => {
    if (!isDragging.current) return;
    isDragging.current = false;
    document.body.style.userSelect = '';
    document.body.style.cursor = '';
  }, []);

  // --- Resize (from bottom-left corner) ---
  const onResizeStart = useCallback((e: React.MouseEvent) => {
    if (maximized || isMobile()) return;
    e.preventDefault();
    e.stopPropagation();
    isResizing.current = true;
    resizeStart.current = {
      mouseX: e.clientX,
      mouseY: e.clientY,
      w: panelState.width,
      h: panelState.height,
    };
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'nesw-resize';
  }, [maximized, panelState.width, panelState.height]);

  const onResizeMove = useCallback((e: MouseEvent) => {
    if (!isResizing.current) return;
    // Drag left edge left = increase width, drag bottom down = increase height
    const dx = resizeStart.current.mouseX - e.clientX;
    const dy = e.clientY - resizeStart.current.mouseY;
    const newW = Math.max(MIN_WIDTH, Math.min(resizeStart.current.w + dx, window.innerWidth - 40));
    const newH = Math.max(MIN_HEIGHT, Math.min(resizeStart.current.h + dy, window.innerHeight - 40));
    setPanelState(prev => {
      // Adjust x position when width changes (panel grows to the left)
      const widthDelta = newW - prev.width;
      const newX = prev.x != null ? prev.x - widthDelta : null;
      return { ...prev, width: newW, height: newH, x: newX != null ? Math.max(0, newX) : null };
    });
  }, []);

  const onResizeEnd = useCallback(() => {
    if (!isResizing.current) return;
    isResizing.current = false;
    document.body.style.userSelect = '';
    document.body.style.cursor = '';
  }, []);

  // Global mouse listeners for drag and resize
  useEffect(() => {
    const handleMove = (e: MouseEvent) => {
      onDragMove(e);
      onResizeMove(e);
    };
    const handleUp = () => {
      onDragEnd();
      onResizeEnd();
    };
    window.addEventListener('mousemove', handleMove);
    window.addEventListener('mouseup', handleUp);
    return () => {
      window.removeEventListener('mousemove', handleMove);
      window.removeEventListener('mouseup', handleUp);
    };
  }, [onDragMove, onDragEnd, onResizeMove, onResizeEnd]);

  const toggleMaximize = useCallback(() => {
    setMaximized(prev => !prev);
  }, []);

  const resetPosition = useCallback(() => {
    setPanelState(prev => ({ ...prev, x: null, y: null }));
  }, []);

  // Build inline style for the panel
  const panelStyle: React.CSSProperties = maximized
    ? {} // maximized class handles it via CSS
    : {
        width: isMobile() ? undefined : panelState.width,
        height: isMobile() ? undefined : panelState.height,
        ...(panelState.x != null && panelState.y != null && !isMobile()
          ? { left: panelState.x, top: panelState.y, right: 'auto', bottom: 'auto' }
          : {}),
      };

  return {
    panelRef,
    panelStyle,
    maximized,
    toggleMaximize,
    onDragStart,
    onResizeStart,
    resetPosition,
  };
}
