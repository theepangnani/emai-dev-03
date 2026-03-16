import { useState, useRef, Suspense } from 'react';
import { courseContentsApi, type CourseContentItem, type CourseContentUpdateResponse } from '../../api/client';
import { ContentCard, MarkdownBody } from '../../components/ContentCard';
import { printElement, downloadAsPdf } from '../../utils/exportUtils';
import { SourceFilesSection, type SourceFilesSectionHandle } from './SourceFilesSection';

interface QuizItem {
  question: string;
  options: Record<string, string>;
  correct_answer: string;
  explanation?: string;
}

interface FlashcardItem {
  front: string;
  back: string;
}

interface DocumentTabProps {
  content: CourseContentItem;
  downloading: boolean;
  onDownload: () => void;
  onShowReplaceModal: () => void;
  onContentUpdated: (result: CourseContentUpdateResponse) => void;
  showToast: (msg: string) => void;
  onShowRegenPrompt: () => void;
  onReloadData: () => Promise<void>;
  onAddMoreFiles?: () => void;
}

function parseFormattedContent(text: string): { type: 'quiz'; data: QuizItem[] } | { type: 'flashcards'; data: FlashcardItem[] } | null {
  const trimmed = text.trim();
  if (!trimmed.startsWith('[')) return null;
  try {
    const parsed = JSON.parse(trimmed);
    if (!Array.isArray(parsed) || parsed.length === 0) return null;
    if (parsed[0].question && parsed[0].options) return { type: 'quiz', data: parsed as QuizItem[] };
    if (parsed[0].front && parsed[0].back) return { type: 'flashcards', data: parsed as FlashcardItem[] };
  } catch { /* not JSON */ }
  return null;
}

function FormattedContent({ textContent, courseContentId }: { textContent: string; courseContentId?: number }) {
  const formatted = parseFormattedContent(textContent);
  if (formatted?.type === 'quiz') {
    return (
      <div className="cm-formatted-quiz">
        {formatted.data.map((q, i) => (
          <div key={i} className="cm-fq-item">
            <p className="cm-fq-question"><strong>Q{i + 1}:</strong> {q.question}</p>
            <ul className="cm-fq-options">
              {Object.entries(q.options || {}).map(([k, v]) => (
                <li key={k} className={k === q.correct_answer ? 'cm-fq-correct' : ''}>
                  <strong>{k}.</strong> {v}
                </li>
              ))}
            </ul>
            {q.explanation && <p className="cm-fq-explanation"><em>{q.explanation}</em></p>}
          </div>
        ))}
      </div>
    );
  }
  if (formatted?.type === 'flashcards') {
    return (
      <div className="cm-formatted-cards">
        {formatted.data.map((c, i) => (
          <div key={i} className="cm-fc-item">
            <strong>{c.front}</strong>
            <span> &mdash; {c.back}</span>
          </div>
        ))}
      </div>
    );
  }
  return (
    <Suspense fallback={<div className="content-card-render-loading">Rendering...</div>}>
      <MarkdownBody content={textContent} courseContentId={courseContentId} />
    </Suspense>
  );
}

export function DocumentTab({
  content,
  downloading,
  onDownload,
  onShowReplaceModal,
  onContentUpdated,
  showToast,
  onShowRegenPrompt,
  onReloadData,
}: DocumentTabProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editTextContent, setEditTextContent] = useState('');
  const [editSaving, setEditSaving] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [addingFiles, setAddingFiles] = useState(false);
  const printRef = useRef<HTMLDivElement>(null);
  const sourceFilesRef = useRef<SourceFilesSectionHandle>(null);
  const addFilesInputRef = useRef<HTMLInputElement>(null);

  const canAddFiles = !content.parent_content_id;

  const handleAddFiles = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setAddingFiles(true);
    try {
      await courseContentsApi.addFilesToMaterial(content.id, Array.from(files));
      showToast('Files added successfully');
      await onReloadData();
    } catch {
      showToast('Failed to add files');
    } finally {
      setAddingFiles(false);
      // Reset input so the same files can be selected again
      if (addFilesInputRef.current) addFilesInputRef.current.value = '';
    }
  };

  const handleStartEdit = () => {
    setEditTextContent(content.text_content || '');
    setIsEditing(true);
  };

  const handleSaveTextContent = async () => {
    setEditSaving(true);
    try {
      const result: CourseContentUpdateResponse = await courseContentsApi.update(content.id, {
        text_content: editTextContent,
      });
      onContentUpdated(result);
      setIsEditing(false);
      if (result.archived_guides_count > 0) {
        showToast(`Content updated. ${result.archived_guides_count} linked study material(s) archived.`);
        onShowRegenPrompt();
        await onReloadData();
      } else {
        showToast('Content saved');
      }
    } catch {
      showToast('Failed to save content');
    } finally {
      setEditSaving(false);
    }
  };

  const hasContent = !!(content.text_content || content.description);

  const handlePrint = () => {
    if (printRef.current) printElement(printRef.current, content.title || 'Document');
  };

  const handleDownloadPdf = async () => {
    if (!printRef.current) return;
    setExporting(true);
    try {
      const filename = (content.title || 'Document').replace(/[^a-zA-Z0-9 _-]/g, '');
      await downloadAsPdf(printRef.current, filename);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="cm-document-tab">
      <div className="cm-tab-card">
        <div className="cm-guide-actions">
          {isEditing ? (
            <>
              <button className="cm-action-btn primary" onClick={handleSaveTextContent} disabled={editSaving}>
                {editSaving ? 'Saving...' : '\u{1F4BE} Save'}
              </button>
              <button className="cm-action-btn" onClick={() => setIsEditing(false)} disabled={editSaving}>Cancel</button>
            </>
          ) : (
            <>
              {hasContent && (
                <>
                  <button className="cm-action-btn" onClick={handlePrint} title="Print">{'\u{1F5A8}\uFE0F'} Print</button>
                  <button className="cm-action-btn" onClick={handleDownloadPdf} disabled={exporting} title="Download PDF">{'\u{1F4E5}'} {exporting ? 'Exporting...' : 'PDF'}</button>
                </>
              )}
              {content.has_file && (
                <button className="cm-action-btn" onClick={onDownload} disabled={downloading}>
                  {downloading ? 'Downloading...' : '\u{1F4CB} Download Original'}
                </button>
              )}
              {!content.has_file && !(content.source_files_count && content.source_files_count > 0) && (
                <button className="cm-action-btn" onClick={handleStartEdit}>{'\u270F\uFE0F'} Edit Content</button>
              )}
              <button className="cm-action-btn" onClick={onShowReplaceModal}>
                {content.has_file ? '\u{1F504} Replace Document' : '\u{1F4E4} Upload Document'}
              </button>
              {canAddFiles && (
                <>
                  <input
                    ref={addFilesInputRef}
                    type="file"
                    multiple
                    accept=".pdf,.docx,.doc,.txt,.md,.xlsx,.xls,.csv,.pptx,.ppt,.png,.jpg,.jpeg,.gif,.bmp,.tiff,.webp,.zip"
                    style={{ display: 'none' }}
                    onChange={handleAddFiles}
                  />
                  <button
                    className="cm-action-btn"
                    onClick={() => addFilesInputRef.current?.click()}
                    disabled={addingFiles}
                  >
                    {addingFiles ? 'Adding...' : '\u{1F4CE} Add More Files'}
                  </button>
                </>
              )}
              {(content.source_files_count ?? 0) > 0 && (
                <button className="cm-action-btn" onClick={() => sourceFilesRef.current?.scrollToAndExpand()}>
                  {'\u{1F4C2}'} Source Files ({content.source_files_count})
                </button>
              )}
            </>
          )}
        </div>
        <div className="cm-tab-card-body">
          {isEditing ? (
            <textarea
              className="cm-edit-textarea"
              value={editTextContent}
              onChange={(e) => setEditTextContent(e.target.value)}
              rows={20}
              disabled={editSaving}
            />
          ) : (
            <div ref={printRef}>
              {content.text_content ? (
                <ContentCard ocrCheckText={content.text_content}>
                  <FormattedContent textContent={content.text_content} courseContentId={content.id} />
                </ContentCard>
              ) : content.has_file ? (
                <div className="cm-file-info-card">
                  <p className="cm-file-info-name">{content.original_filename || 'Uploaded document'}</p>
                  <p className="cm-file-info-hint">Use the Download button above to get the original file.</p>
                </div>
              ) : content.description ? (
                <p className="cm-document-desc">{content.description}</p>
              ) : (
                <p className="cm-empty-message">No document content available.</p>
              )}
            </div>
          )}
        </div>
      </div>
      <SourceFilesSection
        ref={sourceFilesRef}
        contentId={content.id}
        sourceFilesCount={content.source_files_count ?? 0}
        initialExpanded={!content.has_file && (content.source_files_count ?? 0) > 0}
      />

      {content.reference_url && (
        <a href={content.reference_url} target="_blank" rel="noreferrer" className="cm-ref-link">
          View Original Source
        </a>
      )}
    </div>
  );
}
