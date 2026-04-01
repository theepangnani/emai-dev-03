import { useCallback, useRef } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Image from '@tiptap/extension-image';
import Underline from '@tiptap/extension-underline';
import Link from '@tiptap/extension-link';
import Placeholder from '@tiptap/extension-placeholder';
import {
  validateImageFile,
  canAddImages,
  fileToDataUri,
  ALLOWED_EXTENSIONS,
  type ImageValidationError,
} from '../utils/imageValidation';
import './RichTextEditor.css';

interface RichTextEditorProps {
  content: string;
  onUpdate: (html: string, plainText: string) => void;
  placeholder?: string;
  onError?: (error: ImageValidationError) => void;
  readOnly?: boolean;
}

export function RichTextEditor({
  content,
  onUpdate,
  placeholder = 'Start typing your notes...',
  onError,
  readOnly = false,
}: RichTextEditorProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleImageInsert = useCallback(
    async (files: File[], editorInstance: ReturnType<typeof useEditor>) => {
      if (!editorInstance) return;

      const currentHtml = editorInstance.getHTML();
      const countErr = canAddImages(currentHtml, files.length);
      if (countErr) {
        onError?.(countErr);
        return;
      }

      for (const file of files) {
        const validationErr = validateImageFile(file);
        if (validationErr) {
          onError?.(validationErr);
          return;
        }

        try {
          const dataUri = await fileToDataUri(file);
          editorInstance.chain().focus().setImage({ src: dataUri }).run();
        } catch {
          onError?.({
            type: 'format',
            message: 'Failed to read image file.',
          });
        }
      }
    },
    [onError],
  );

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
      }),
      Underline,
      Link.configure({
        openOnClick: false,
        HTMLAttributes: { rel: 'noopener noreferrer', target: '_blank' },
      }),
      Image.configure({
        inline: false,
        allowBase64: true,
        HTMLAttributes: {
          class: 'note-image',
        },
      }),
      Placeholder.configure({
        placeholder,
      }),
    ],
    content,
    editable: !readOnly,
    onUpdate: ({ editor: e }) => {
      const html = e.getHTML();
      const text = e.getText();
      onUpdate(html, text);
    },
    editorProps: {
      handleDrop: (_view: unknown, event: DragEvent, _slice: unknown, moved: boolean) => {
        if (moved || !event.dataTransfer?.files?.length) return false;

        const files = Array.from(event.dataTransfer.files).filter((f: File) =>
          f.type.startsWith('image/'),
        );
        if (files.length === 0) return false;

        event.preventDefault();
        handleImageInsert(files, editor);
        return true;
      },
      handlePaste: (_view: unknown, event: ClipboardEvent) => {
        const items = event.clipboardData?.items;
        if (!items) return false;

        const imageFiles: File[] = [];
        for (const item of Array.from(items)) {
          if (item.type.startsWith('image/')) {
            const file = (item as DataTransferItem).getAsFile();
            if (file) imageFiles.push(file);
          }
        }

        if (imageFiles.length === 0) return false;

        event.preventDefault();
        handleImageInsert(imageFiles, editor);
        return true;
      },
    },
  });

  const handleFileUpload = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (!files?.length) return;
      handleImageInsert(Array.from(files), editor);
      // Reset input so the same file can be selected again
      e.target.value = '';
    },
    [editor, handleImageInsert],
  );

  if (!editor) return null;

  return (
    <div className="rte-container">
      {!readOnly && (
        <div className="rte-toolbar" role="toolbar" aria-label="Text formatting">
          <div className="rte-toolbar-group">
            <button
              type="button"
              className={`rte-btn ${editor.isActive('bold') ? 'rte-btn--active' : ''}`}
              onClick={() => editor.chain().focus().toggleBold().run()}
              title="Bold (Ctrl+B)"
              aria-label="Bold"
              aria-pressed={editor.isActive('bold')}
            >
              <strong>B</strong>
            </button>
            <button
              type="button"
              className={`rte-btn ${editor.isActive('italic') ? 'rte-btn--active' : ''}`}
              onClick={() => editor.chain().focus().toggleItalic().run()}
              title="Italic (Ctrl+I)"
              aria-label="Italic"
              aria-pressed={editor.isActive('italic')}
            >
              <em>I</em>
            </button>
            <button
              type="button"
              className={`rte-btn ${editor.isActive('underline') ? 'rte-btn--active' : ''}`}
              onClick={() => editor.chain().focus().toggleUnderline().run()}
              title="Underline (Ctrl+U)"
              aria-label="Underline"
              aria-pressed={editor.isActive('underline')}
            >
              <u>U</u>
            </button>
            <button
              type="button"
              className={`rte-btn ${editor.isActive('strike') ? 'rte-btn--active' : ''}`}
              onClick={() => editor.chain().focus().toggleStrike().run()}
              title="Strikethrough"
              aria-label="Strikethrough"
              aria-pressed={editor.isActive('strike')}
            >
              <s>S</s>
            </button>
          </div>

          <div className="rte-toolbar-divider" />

          <div className="rte-toolbar-group">
            <button
              type="button"
              className={`rte-btn ${editor.isActive('heading', { level: 1 }) ? 'rte-btn--active' : ''}`}
              onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
              title="Heading 1"
              aria-label="Heading 1"
              aria-pressed={editor.isActive('heading', { level: 1 })}
            >
              H1
            </button>
            <button
              type="button"
              className={`rte-btn ${editor.isActive('heading', { level: 2 }) ? 'rte-btn--active' : ''}`}
              onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
              title="Heading 2"
              aria-label="Heading 2"
              aria-pressed={editor.isActive('heading', { level: 2 })}
            >
              H2
            </button>
            <button
              type="button"
              className={`rte-btn ${editor.isActive('heading', { level: 3 }) ? 'rte-btn--active' : ''}`}
              onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
              title="Heading 3"
              aria-label="Heading 3"
              aria-pressed={editor.isActive('heading', { level: 3 })}
            >
              H3
            </button>
          </div>

          <div className="rte-toolbar-divider" />

          <div className="rte-toolbar-group">
            <button
              type="button"
              className={`rte-btn ${editor.isActive('bulletList') ? 'rte-btn--active' : ''}`}
              onClick={() => editor.chain().focus().toggleBulletList().run()}
              title="Bullet list"
              aria-label="Bullet list"
              aria-pressed={editor.isActive('bulletList')}
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <circle cx="3" cy="4" r="1.5" fill="currentColor" />
                <circle cx="3" cy="8" r="1.5" fill="currentColor" />
                <circle cx="3" cy="12" r="1.5" fill="currentColor" />
                <path d="M6.5 4h7M6.5 8h7M6.5 12h7" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
              </svg>
            </button>
            <button
              type="button"
              className={`rte-btn ${editor.isActive('orderedList') ? 'rte-btn--active' : ''}`}
              onClick={() => editor.chain().focus().toggleOrderedList().run()}
              title="Numbered list"
              aria-label="Numbered list"
              aria-pressed={editor.isActive('orderedList')}
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <text x="1.5" y="5.5" fontSize="5" fill="currentColor" fontWeight="bold">1</text>
                <text x="1.5" y="9.5" fontSize="5" fill="currentColor" fontWeight="bold">2</text>
                <text x="1.5" y="13.5" fontSize="5" fill="currentColor" fontWeight="bold">3</text>
                <path d="M6.5 4h7M6.5 8h7M6.5 12h7" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
              </svg>
            </button>
            <button
              type="button"
              className={`rte-btn ${editor.isActive('blockquote') ? 'rte-btn--active' : ''}`}
              onClick={() => editor.chain().focus().toggleBlockquote().run()}
              title="Block quote"
              aria-label="Block quote"
              aria-pressed={editor.isActive('blockquote')}
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path d="M3 3v10M6 5h7M6 8h5M6 11h6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
              </svg>
            </button>
          </div>

          <div className="rte-toolbar-divider" />

          <div className="rte-toolbar-group">
            <button
              type="button"
              className="rte-btn"
              onClick={handleFileUpload}
              title="Insert image"
              aria-label="Insert image"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <rect x="1.5" y="2.5" width="13" height="11" rx="1.5" stroke="currentColor" strokeWidth="1.3" />
                <circle cx="5" cy="6" r="1.5" stroke="currentColor" strokeWidth="1" />
                <path d="M1.5 11l3.5-3 3 2.5 2-1.5 4.5 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept={ALLOWED_EXTENSIONS.join(',')}
              multiple
              onChange={handleFileChange}
              style={{ display: 'none' }}
            />
          </div>
        </div>
      )}
      <EditorContent editor={editor} className="rte-content" aria-label="Rich text editor" />
    </div>
  );
}
