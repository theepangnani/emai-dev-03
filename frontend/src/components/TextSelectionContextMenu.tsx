import { useState, useEffect, useCallback, useRef } from 'react';
import './TextSelectionContextMenu.css';

interface ContextMenuPosition {
  x: number;
  y: number;
}

interface TextSelectionContextMenuProps {
  /** The container element to attach the context menu to */
  containerRef: React.RefObject<HTMLElement | null>;
  /** Callback when "Add Note" is selected */
  onAddNote?: (selectedText: string) => void;
  /** Callback when "Ask Chat Bot" is selected */
  onAskChatBot?: (selectedText: string) => void;
}

export function TextSelectionContextMenu({
  containerRef,
  onAddNote,
  onAskChatBot,
}: TextSelectionContextMenuProps) {
  const [visible, setVisible] = useState(false);
  const [position, setPosition] = useState<ContextMenuPosition>({ x: 0, y: 0 });
  const [selectedText, setSelectedText] = useState('');
  const menuRef = useRef<HTMLDivElement>(null);

  const handleContextMenu = useCallback((e: MouseEvent) => {
    const selection = window.getSelection();
    const text = selection?.toString().trim();

    if (!text || text.length < 3) return; // Need meaningful selection

    e.preventDefault();
    setSelectedText(text);
    setPosition({ x: e.clientX, y: e.clientY });
    setVisible(true);
  }, []);

  const handleClose = useCallback(() => {
    setVisible(false);
    setSelectedText('');
  }, []);

  const handleAction = useCallback((action: 'note' | 'ask_chatbot') => {
    const text = selectedText;
    handleClose();

    switch (action) {
      case 'note':
        onAddNote?.(text);
        break;
      case 'ask_chatbot':
        onAskChatBot?.(text);
        break;
    }
  }, [selectedText, handleClose, onAddNote, onAskChatBot]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    container.addEventListener('contextmenu', handleContextMenu);
    return () => container.removeEventListener('contextmenu', handleContextMenu);
  }, [containerRef, handleContextMenu]);

  // Close on click outside or Escape
  useEffect(() => {
    if (!visible) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        handleClose();
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleClose();
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [visible, handleClose]);

  if (!visible) return null;

  return (
    <div
      ref={menuRef}
      className="text-selection-context-menu"
      style={{
        position: 'fixed',
        left: position.x,
        top: position.y,
        zIndex: 9999,
      }}
    >
      {onAddNote && (
        <button
          className="context-menu-item"
          onClick={() => handleAction('note')}
        >
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path d="M4 2h8a2 2 0 012 2v8a2 2 0 01-2 2H4a2 2 0 01-2-2V4a2 2 0 012-2z" stroke="currentColor" strokeWidth="1.3"/>
            <path d="M5 6h6M5 8.5h6M5 11h3.5" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round"/>
          </svg>
          Add Note
        </button>
      )}
      {onAskChatBot && (
        <>
          <div className="context-menu-divider" />
          <button
            className="context-menu-item"
            onClick={() => handleAction('ask_chatbot')}
            title="Ask the chatbot about this text"
          >
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path d="M2 3a1 1 0 011-1h10a1 1 0 011 1v7a1 1 0 01-1 1H5l-3 3V3z" stroke="currentColor" strokeWidth="1.3"/>
            </svg>
            Ask Chat Bot
          </button>
        </>
      )}
    </div>
  );
}
