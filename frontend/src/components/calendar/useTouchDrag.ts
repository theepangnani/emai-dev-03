import { useRef, useCallback } from 'react';

interface DragData {
  id: number;
  itemType: string;
}

/**
 * Hook that adds touch-based drag-and-drop alongside native HTML5 drag-and-drop.
 * Uses a 300ms long-press to differentiate drag from scroll.
 * Returns handlers for drag source (entries) and drop targets (day cells / week columns).
 */
export function useTouchDrag(onTaskDrop?: (taskId: number, newDate: Date) => void) {
  const dragDataRef = useRef<DragData | null>(null);
  const dragGhostRef = useRef<HTMLDivElement | null>(null);
  const activeDropZoneRef = useRef<HTMLElement | null>(null);
  const pressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isDraggingRef = useRef(false);
  const sourceElRef = useRef<HTMLElement | null>(null);

  // --- Source handlers (CalendarEntry) ---

  const handleTouchStart = useCallback((e: React.TouchEvent, data: DragData) => {
    const taskEl = (e.target as HTMLElement).closest('[draggable]') as HTMLElement | null;
    if (!taskEl) return;

    dragDataRef.current = data;
    sourceElRef.current = taskEl;
    const touch = e.touches[0];
    const text = taskEl.textContent?.slice(0, 30) || 'Task';

    // Start long-press timer (300ms)
    pressTimerRef.current = setTimeout(() => {
      isDraggingRef.current = true;

      // Haptic feedback on supported devices
      navigator.vibrate?.(30);

      // Add dragging class to source element
      taskEl.classList.add('cal-entry-dragging');

      // Add is-dragging class to calendar container
      const container = taskEl.closest('.calendar-container');
      container?.classList.add('is-dragging');

      // Create visual ghost element
      const ghost = document.createElement('div');
      ghost.className = 'cal-drag-ghost';
      ghost.textContent = text;
      ghost.style.left = `${touch.clientX}px`;
      ghost.style.top = `${touch.clientY}px`;
      document.body.appendChild(ghost);
      dragGhostRef.current = ghost;
    }, 300);
  }, []);

  const handleTouchMove = useCallback((e: React.TouchEvent) => {
    // If timer still running (user is scrolling), cancel drag
    if (pressTimerRef.current && !isDraggingRef.current) {
      clearTimeout(pressTimerRef.current);
      pressTimerRef.current = null;
      dragDataRef.current = null;
      sourceElRef.current = null;
      return;
    }

    if (!isDraggingRef.current) return;

    e.preventDefault(); // Prevent scroll during drag

    const touch = e.touches[0];

    // Move ghost
    if (dragGhostRef.current) {
      dragGhostRef.current.style.left = `${touch.clientX}px`;
      dragGhostRef.current.style.top = `${touch.clientY}px`;
    }

    // Find drop zone under finger
    const elementUnder = document.elementFromPoint(touch.clientX, touch.clientY);
    const dropZone = elementUnder?.closest('[data-drop-date]') as HTMLElement | null;

    // Clear previous highlight
    if (activeDropZoneRef.current && activeDropZoneRef.current !== dropZone) {
      activeDropZoneRef.current.classList.remove('cal-day-drag-over');
    }

    // Highlight new drop zone
    if (dropZone) {
      dropZone.classList.add('cal-day-drag-over');
      activeDropZoneRef.current = dropZone;
    } else {
      activeDropZoneRef.current = null;
    }
  }, []);

  const handleTouchEnd = useCallback(() => {
    // Clear long-press timer
    if (pressTimerRef.current) {
      clearTimeout(pressTimerRef.current);
      pressTimerRef.current = null;
    }

    // Clean up ghost
    if (dragGhostRef.current) {
      dragGhostRef.current.remove();
      dragGhostRef.current = null;
    }

    // Remove dragging class from source element
    if (sourceElRef.current) {
      sourceElRef.current.classList.remove('cal-entry-dragging');
    }

    // Remove is-dragging from container
    const container = sourceElRef.current?.closest('.calendar-container');
    container?.classList.remove('is-dragging');

    // Clear highlight
    if (activeDropZoneRef.current) {
      activeDropZoneRef.current.classList.remove('cal-day-drag-over');
    }

    if (!isDraggingRef.current) {
      dragDataRef.current = null;
      sourceElRef.current = null;
      return;
    }

    isDraggingRef.current = false;

    // Execute drop
    if (dragDataRef.current && activeDropZoneRef.current && onTaskDrop) {
      const dateStr = activeDropZoneRef.current.getAttribute('data-drop-date');
      if (dateStr) {
        const [y, m, d] = dateStr.split('-').map(Number);
        const newDate = new Date(y, m - 1, d);
        onTaskDrop(dragDataRef.current.id, newDate);
      }
    }

    dragDataRef.current = null;
    activeDropZoneRef.current = null;
    sourceElRef.current = null;
  }, [onTaskDrop]);

  return { handleTouchStart, handleTouchMove, handleTouchEnd };
}
