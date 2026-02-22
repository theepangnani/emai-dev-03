import { useState, Suspense } from 'react';
import { courseContentsApi, type CourseContentItem, type CourseContentUpdateResponse } from '../../api/client';
import { ContentCard, MarkdownBody } from '../../components/ContentCard';
import { AddActionButton } from '../../components/AddActionButton';

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
}

function FormattedContent({ textContent }: { textContent: string }) {
  const trimmed = textContent.trim();
  if (trimmed.startsWith('[')) {
    try {
      const parsed = JSON.parse(trimmed);
      if (Array.isArray(parsed) && parsed.length > 0) {
        if (parsed[0].question && parsed[0].options) {
          return (
            <div className="cm-formatted-quiz">
              {(parsed as QuizItem[]).map((q, i) => (
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
        if (parsed[0].front && parsed[0].back) {
          return (
            <div className="cm-formatted-cards">
              {(parsed as FlashcardItem[]).map((c, i) => (
                <div key={i} className="cm-fc-item">
                  <strong>{c.front}</strong>
                  <span> &mdash; {c.back}</span>
                </div>
              ))}
            </div>
          );
        }
      }
    } catch { /* not JSON, fall through to markdown */ }
  }
  return (
    <Suspense fallback={<div className="content-card-render-loading">Rendering...</div>}>
      <MarkdownBody content={textContent} />
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

  return (
    <div className="cm-document-tab">
      {isEditing ? (
        <div className="cm-guide-actions">
          <button className="cm-action-btn" onClick={handleSaveTextContent} disabled={editSaving}>
            {editSaving ? 'Saving...' : 'Save'}
          </button>
          <button className="cm-action-btn" onClick={() => setIsEditing(false)} disabled={editSaving}>Cancel</button>
        </div>
      ) : (
        <div className="cm-document-actions">
          <AddActionButton actions={[
            ...(content.has_file ? [{
              icon: '\u{1F4E5}',
              label: downloading ? 'Downloading...' : 'Download',
              onClick: onDownload,
            }] : []),
            ...(!content.has_file ? [{
              icon: '\u270F\uFE0F',
              label: 'Edit Content',
              onClick: handleStartEdit,
            }] : []),
            {
              icon: '\u{1F4C4}',
              label: content.has_file ? 'Replace Document' : 'Upload Document',
              onClick: onShowReplaceModal,
            },
          ]} />
        </div>
      )}
      {isEditing ? (
        <textarea
          className="cm-edit-textarea"
          value={editTextContent}
          onChange={(e) => setEditTextContent(e.target.value)}
          rows={20}
          disabled={editSaving}
        />
      ) : content.text_content ? (
        <ContentCard ocrCheckText={content.text_content}>
          <FormattedContent textContent={content.text_content} />
        </ContentCard>
      ) : content.has_file ? (
        <div className="cm-file-info-card">
          <p className="cm-file-info-name">{content.original_filename || 'Uploaded document'}</p>
          <p className="cm-file-info-hint">Use the + button above to download the original file.</p>
        </div>
      ) : content.description ? (
        <p className="cm-document-desc">{content.description}</p>
      ) : (
        <p className="cm-empty-message">No document content available.</p>
      )}
      {content.reference_url && (
        <a href={content.reference_url} target="_blank" rel="noreferrer" className="cm-ref-link">
          View Original Source
        </a>
      )}
    </div>
  );
}
