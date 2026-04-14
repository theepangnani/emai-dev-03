import { useState, useRef, useCallback, useEffect } from 'react';

const MIN_WIDTH = 320;
const MIN_HEIGHT = 380;
const DEFAULT_WIDTH = 400;
const DEFAULT_HEIGHT = 520;
const DEFAULT_STORAGE_KEY = 'classbridge-chat-panel-state';

interface PanelState {
  width: number;
  height: number;
  x: number | null;
  y: number | null;
}

function loadState(key: string): PanelState {
  try {
    const raw = localStorage.getItem(key);
    if (raw) {
      const parsed = JSON.parse(raw);
      const state: PanelState = {
        width: Math.max(MIN_WIDTH, parsed.width ?? DEFAULT_WIDTH),
        height: Math.max(MIN_HEIGHT, parsed.height ?? DEFAULT_HEIGHT),
        x: typeof parsed.x === 'number' ? parsed.x : null,
        y: typeof parsed.y === 'number' ? parsed.y : null,
      };
      // Clamp saved position to current viewport (#3341 related)
      if (state.x != null && state.y != null) {
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        state.x = Math.max(0, Math.min(state.x, vw - state.width));
        state.y = Math.max(0, Math.min(state.y, vh - state.height));
      }
      return state;
    }
  } catch { /* ignore */ }
  return { width: DEFAULT_WIDTH, height: DEFAULT_HEIGHT, x: null, y: null };
}

function saveState(key: string, state: PanelState) {
  try {
    localStorage.setItem(key, JSON.stringify(state));
  } catch { /* ignore */ }
}

/** #3338: Accept storageKey param to avoid collision between SpeedDialFAB and HelpChatbot */
export function useChatPanelInteraction(storageKey: string = DEFAULT_STORAGE_KEY) {
  const [maximized, setMaximized] = useState(false);
  const [panelState, setPanelState] = useState<PanelState>(() => loadState(storageKey));
  const panelRef = useRef<HTMLDivElement>(null);
  const isDragging = useRef(false);
  const isResizing = useRef(false);
  const dragStart = useRef({ mouseX: 0, mouseY: 0, panelX: 0, panelY: 0 });
  const resizeStart = useRef({ mouseX: 0, mouseY: 0, w: 0, h: 0 });

  // #3340: Use ref for panelState to avoid stale closures in move callbacks
  const panelStateRef = useRef(panelState);
  useEffect(() => {
    panelStateRef.current = panelState;
  }, [panelState]);

  // #3341: Reactive mobile detection
  const [mobile, setMobile] = useState(() => window.innerWidth < 768);
  useEffect(() => {
    const onResize = () => setMobile(window.innerWidth < 768);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  // Persist state changes
  useEffect(() => {
    if (!maximized) saveState(storageKey, panelState);
  }, [panelState, maximized, storageKey]);

  // #3339 + #3340: Use stable refs for move/end handlers to avoid re-render cascades
  // Handlers are stored in refs so global listeners don't need to be re-attached
  const handlePointerMove = useRef((e: PointerEvent) => {
    if (isDragging.current) {
      const dx = e.clientX - dragStart.current.mouseX;
      const dy = e.clientY - dragStart.current.mouseY;
      const newX = dragStart.current.panelX + dx;
      const newY = dragStart.current.panelY + dy;
      const { width, height } = panelStateRef.current;
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      const clampedX = Math.max(0, Math.min(newX, vw - width));
      const clampedY = Math.max(0, Math.min(newY, vh - height));
      setPanelState(prev => ({ ...prev, x: clampedX, y: clampedY }));
    }
    if (isResizing.current) {
      const dx = resizeStart.current.mouseX - e.clientX;
      const dy = e.clientY - resizeStart.current.mouseY;
      const newW = Math.max(MIN_WIDTH, Math.min(resizeStart.current.w + dx, window.innerWidth - 40));
      const newH = Math.max(MIN_HEIGHT, Math.min(resizeStart.current.h + dy, window.innerHeight - 40));
      setPanelState(prev => {
        const widthDelta = newW - prev.width;
        const newX = prev.x != null ? prev.x - widthDelta : null;
        return { ...prev, width: newW, height: newH, x: newX != null ? Math.max(0, newX) : null };
      });
    }
  });

  const handlePointerUp = useRef(() => {
    if (isDragging.current || isResizing.current) {
      isDragging.current = false;
      isResizing.current = false;
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
      // #3339: Detach listeners when interaction ends
      window.removeEventListener('pointermove', handlePointerMove.current);
      window.removeEventListener('pointerup', handlePointerUp.current);
    }
  });

  // #3343: Use pointer events for unified mouse + touch support
  const onDragStart = useCallback((e: React.PointerEvent) => {
    if (maximized || mobile) return;
    if ((e.target as HTMLElement).closest('button')) return;
    e.preventDefault();
    isDragging.current = true;

    const panel = panelRef.current;
    if (!panel) return;
    const rect = panel.getBoundingClientRect();
    const currentX = panelStateRef.current.x ?? rect.left;
    const currentY = panelStateRef.current.y ?? rect.top;
    dragStart.current = { mouseX: e.clientX, mouseY: e.clientY, panelX: currentX, panelY: currentY };
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'grabbing';
    // #3339: Attach listeners only when interaction starts
    window.addEventListener('pointermove', handlePointerMove.current);
    window.addEventListener('pointerup', handlePointerUp.current);
  }, [maximized, mobile]);

  const onResizeStart = useCallback((e: React.PointerEvent) => {
    if (maximized || mobile) return;
    e.preventDefault();
    e.stopPropagation();
    isResizing.current = true;
    resizeStart.current = {
      mouseX: e.clientX,
      mouseY: e.clientY,
      w: panelStateRef.current.width,
      h: panelStateRef.current.height,
    };
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'nesw-resize';
    // #3339: Attach listeners only when interaction starts
    window.addEventListener('pointermove', handlePointerMove.current);
    window.addEventListener('pointerup', handlePointerUp.current);
  }, [maximized, mobile]);

  const toggleMaximize = useCallback(() => {
    setMaximized(prev => !prev);
  }, []);

  // Build inline style for the panel
  const panelStyle: React.CSSProperties = maximized
    ? {}
    : {
        width: mobile ? undefined : panelState.width,
        height: mobile ? undefined : panelState.height,
        ...(panelState.x != null && panelState.y != null && !mobile
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
  };
}
