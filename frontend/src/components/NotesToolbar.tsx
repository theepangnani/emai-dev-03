import type { Editor } from '@tiptap/react';
import { useCallback, useState, useRef, useEffect } from 'react';

interface NotesToolbarProps {
  editor: Editor | null;
}

const HIGHLIGHT_COLORS = [
  { label: 'Yellow', color: '#fef08a' },
  { label: 'Green', color: '#bbf7d0' },
  { label: 'Blue', color: '#bfdbfe' },
  { label: 'Pink', color: '#fbcfe8' },
];

export function NotesToolbar({ editor }: NotesToolbarProps) {
  const [showHighlightPicker, setShowHighlightPicker] = useState(false);
  const [showLinkInput, setShowLinkInput] = useState(false);
  const [linkUrl, setLinkUrl] = useState('');
  const highlightRef = useRef<HTMLDivElement>(null);
  const linkRef = useRef<HTMLDivElement>(null);

  // Close dropdowns on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (highlightRef.current && !highlightRef.current.contains(e.target as Node)) {
        setShowHighlightPicker(false);
      }
      if (linkRef.current && !linkRef.current.contains(e.target as Node)) {
        setShowLinkInput(false);
        setLinkUrl('');
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const setLink = useCallback(() => {
    if (!editor) return;
    if (!linkUrl) {
      editor.chain().focus().extendMarkRange('link').unsetLink().run();
    } else {
      const trimmed = linkUrl.trim();
      // Block dangerous protocols
      if (/^javascript:/i.test(trimmed) || /^data:/i.test(trimmed) || /^vbscript:/i.test(trimmed)) return;
      const url = trimmed.startsWith('http') ? trimmed : `https://${trimmed}`;
      editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run();
    }
    setShowLinkInput(false);
    setLinkUrl('');
  }, [editor, linkUrl]);

  const openLinkInput = useCallback(() => {
    if (!editor) return;
    const prev = editor.getAttributes('link').href || '';
    setLinkUrl(prev);
    setShowLinkInput(true);
  }, [editor]);

  if (!editor) return null;

  return (
    <div className="notes-toolbar" role="toolbar" aria-label="Text formatting">
      <button
        type="button"
        className={`notes-tb-btn${editor.isActive('bold') ? ' active' : ''}`}
        onClick={() => editor.chain().focus().toggleBold().run()}
        title="Bold"
        aria-label="Bold"
        aria-pressed={editor.isActive('bold')}
      >
        <strong>B</strong>
      </button>
      <button
        type="button"
        className={`notes-tb-btn${editor.isActive('italic') ? ' active' : ''}`}
        onClick={() => editor.chain().focus().toggleItalic().run()}
        title="Italic"
        aria-label="Italic"
        aria-pressed={editor.isActive('italic')}
      >
        <em>I</em>
      </button>
      <button
        type="button"
        className={`notes-tb-btn${editor.isActive('underline') ? ' active' : ''}`}
        onClick={() => editor.chain().focus().toggleUnderline().run()}
        title="Underline"
        aria-label="Underline"
        aria-pressed={editor.isActive('underline')}
      >
        <span style={{ textDecoration: 'underline' }}>U</span>
      </button>
      <button
        type="button"
        className={`notes-tb-btn${editor.isActive('strike') ? ' active' : ''}`}
        onClick={() => editor.chain().focus().toggleStrike().run()}
        title="Strikethrough"
        aria-label="Strikethrough"
        aria-pressed={editor.isActive('strike')}
      >
        <span style={{ textDecoration: 'line-through' }}>S</span>
      </button>

      <span className="notes-tb-sep" />

      <button
        type="button"
        className={`notes-tb-btn${editor.isActive('heading', { level: 1 }) ? ' active' : ''}`}
        onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
        title="Heading 1"
        aria-label="Heading 1"
      >
        H1
      </button>
      <button
        type="button"
        className={`notes-tb-btn${editor.isActive('heading', { level: 2 }) ? ' active' : ''}`}
        onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
        title="Heading 2"
        aria-label="Heading 2"
      >
        H2
      </button>
      <button
        type="button"
        className={`notes-tb-btn${editor.isActive('heading', { level: 3 }) ? ' active' : ''}`}
        onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
        title="Heading 3"
        aria-label="Heading 3"
      >
        H3
      </button>

      <span className="notes-tb-sep" />

      <button
        type="button"
        className={`notes-tb-btn${editor.isActive('bulletList') ? ' active' : ''}`}
        onClick={() => editor.chain().focus().toggleBulletList().run()}
        title="Bullet list"
        aria-label="Bullet list"
      >
        &#8226;
      </button>
      <button
        type="button"
        className={`notes-tb-btn${editor.isActive('orderedList') ? ' active' : ''}`}
        onClick={() => editor.chain().focus().toggleOrderedList().run()}
        title="Numbered list"
        aria-label="Numbered list"
      >
        1.
      </button>
      <button
        type="button"
        className={`notes-tb-btn${editor.isActive('blockquote') ? ' active' : ''}`}
        onClick={() => editor.chain().focus().toggleBlockquote().run()}
        title="Blockquote"
        aria-label="Blockquote"
      >
        &#8220;
      </button>
      <button
        type="button"
        className={`notes-tb-btn${editor.isActive('codeBlock') ? ' active' : ''}`}
        onClick={() => editor.chain().focus().toggleCodeBlock().run()}
        title="Code block"
        aria-label="Code block"
      >
        {'</>'}
      </button>

      <span className="notes-tb-sep" />

      <div className="notes-tb-dropdown-wrapper" ref={highlightRef}>
        <button
          type="button"
          className={`notes-tb-btn${editor.isActive('highlight') ? ' active' : ''}`}
          onClick={() => setShowHighlightPicker(!showHighlightPicker)}
          title="Highlight"
          aria-label="Highlight"
          aria-expanded={showHighlightPicker}
        >
          <span className="notes-tb-highlight-icon">H</span>
        </button>
        {showHighlightPicker && (
          <div className="notes-tb-dropdown">
            {HIGHLIGHT_COLORS.map(({ label, color }) => (
              <button
                key={color}
                type="button"
                className="notes-tb-color-btn"
                style={{ backgroundColor: color }}
                title={label}
                onClick={() => {
                  editor.chain().focus().toggleHighlight({ color }).run();
                  setShowHighlightPicker(false);
                }}
              />
            ))}
            {editor.isActive('highlight') && (
              <button
                type="button"
                className="notes-tb-color-btn notes-tb-color-clear"
                title="Remove highlight"
                onClick={() => {
                  editor.chain().focus().unsetHighlight().run();
                  setShowHighlightPicker(false);
                }}
              >
                &times;
              </button>
            )}
          </div>
        )}
      </div>

      <div className="notes-tb-dropdown-wrapper" ref={linkRef}>
        <button
          type="button"
          className={`notes-tb-btn${editor.isActive('link') ? ' active' : ''}`}
          onClick={openLinkInput}
          title="Link"
          aria-label="Insert link"
          aria-expanded={showLinkInput}
        >
          &#128279;
        </button>
        {showLinkInput && (
          <div className="notes-tb-dropdown notes-tb-link-input">
            <input
              type="url"
              placeholder="https://..."
              value={linkUrl}
              onChange={e => setLinkUrl(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') setLink(); if (e.key === 'Escape') { setShowLinkInput(false); setLinkUrl(''); } }}
              aria-label="URL"
              autoFocus
            />
            <button type="button" onClick={setLink}>
              {linkUrl ? 'Set' : 'Remove'}
            </button>
          </div>
        )}
      </div>

      <span className="notes-tb-sep" />

      <button
        type="button"
        className="notes-tb-btn"
        onClick={() => editor.chain().focus().undo().run()}
        disabled={!editor.can().undo()}
        title="Undo"
        aria-label="Undo"
      >
        &#8617;
      </button>
      <button
        type="button"
        className="notes-tb-btn"
        onClick={() => editor.chain().focus().redo().run()}
        disabled={!editor.can().redo()}
        title="Redo"
        aria-label="Redo"
      >
        &#8618;
      </button>
    </div>
  );
}
