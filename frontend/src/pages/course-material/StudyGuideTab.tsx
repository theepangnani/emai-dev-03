import { Suspense, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import type { StudyGuide } from '../../api/client';
import type { TaskItem } from '../../api/tasks';
import { studyApi } from '../../api/study';
import { classifyDocument } from '../../api/study';
import { ContentCard, MarkdownBody, MarkdownErrorBoundary } from '../../components/ContentCard';
import { FormatSelector, type StudyFormat } from '../../components/study/FormatSelector';
import { GenerationSpinner } from '../../components/GenerationSpinner';
import { StreamingMarkdown } from '../../components/StreamingMarkdown';
import DocumentTypeSelector from '../../components/DocumentTypeSelector';
import StudyGoalSelector from '../../components/StudyGoalSelector';
import { printElement, downloadAsPdf } from '../../utils/exportUtils';
import { LinkedTasksBanner } from './LinkedTasksBanner';
import { ContentMetaBar } from './ContentMetaBar';
import ParentSummaryCard from '../../components/ParentSummaryCard';
import StudyGuideSuggestionChips, { type SuggestionTopic } from '../../components/StudyGuideSuggestionChips';

interface StudyGuideTabProps {
  studyGuide: StudyGuide | undefined;
  generating: string | null;
  focusPrompt: string;
  onFocusPromptChange: (value: string) => void;
  onGenerate: (options?: { documentType?: string; studyGoal?: string; studyGoalText?: string }) => void;
  onDelete: (guide: StudyGuide) => void;
  hasSourceContent: boolean;
  linkedTasks?: TaskItem[];
  atLimit?: boolean;
  courseContentId?: number;
  onFormatSelect?: (format: StudyFormat) => void;
  onViewDocument?: () => void;
  onContinue?: () => void;
  streamingContent?: string;
  isStreaming?: boolean;
  streamStatus?: string;
  courseName?: string | null;
  createdAt?: string | null;
  courseId?: number;
  /** Text content for auto-classification */
  textContent?: string;
  /** Original filename for auto-classification */
  originalFilename?: string;
  /** Saved document type from CourseContent */
  savedDocumentType?: string;
  /** Saved study goal from CourseContent */
  savedStudyGoal?: string;
  /** Saved study goal text from CourseContent */
  savedStudyGoalText?: string;
  onGenerateChildGuide?: (topic: string, guideType: string) => void | Promise<void>;
  childGuideGenerating?: string | null;
}

function FocusIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.3"/>
      <circle cx="8" cy="8" r="2.5" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M8 1v2M8 13v2M1 8h2M13 8h2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
    </svg>
  );
}

function EmptyGuideIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M4 4h4l2 2h8a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6a2 2 0 012-2z" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M8 12h8M8 15h5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
    </svg>
  );
}

export function StudyGuideTab({
  studyGuide,
  generating,
  focusPrompt,
  onFocusPromptChange,
  onGenerate,
  onDelete,
  hasSourceContent,
  linkedTasks = [],
  atLimit = false,
  courseContentId,
  onFormatSelect,
  onViewDocument,
  onContinue,
  streamingContent,
  isStreaming,
  streamStatus,
  courseName,
  createdAt,
  courseId,
  textContent,
  originalFilename,
  savedDocumentType,
  savedStudyGoal,
  savedStudyGoalText,
  onGenerateChildGuide,
  childGuideGenerating,
}: StudyGuideTabProps) {
  const printRef = useRef<HTMLDivElement>(null);
  const [exporting, setExporting] = useState(false);
  const [continuing, setContinuing] = useState(false);

  // Document type & study goal state for empty state generation controls
  const [documentType, setDocumentType] = useState(savedDocumentType || '');
  const [autoDetectedType, setAutoDetectedType] = useState<string | null>(null);
  const [autoConfidence, setAutoConfidence] = useState(0);
  const [studyGoal, setStudyGoal] = useState(savedStudyGoal || '');
  const [studyGoalText, setStudyGoalText] = useState(savedStudyGoalText || '');

  // Auto-detect document type when empty state is shown
  useEffect(() => {
    if (studyGuide) return; // Only classify when no guide exists
    let cancelled = false;
    const text = (textContent || '').trim();
    const filename = originalFilename || '';
    if (!text && !filename) return;

    classifyDocument(text.slice(0, 2000), filename)
      .then((result) => {
        if (cancelled) return;
        setAutoDetectedType(result.document_type);
        setAutoConfidence(result.confidence);
        if (!documentType) {
          setDocumentType(result.document_type);
        }
      })
      .catch(() => { /* auto-detect is best-effort */ });

    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [studyGuide, textContent, originalFilename]);

  const handlePrint = () => {
    if (printRef.current) printElement(printRef.current, studyGuide?.title || 'Study Guide');
  };

  const handleDownloadPdf = async () => {
    if (!printRef.current) return;
    setExporting(true);
    try {
      const filename = (studyGuide?.title || 'Study Guide').replace(/[^a-zA-Z0-9 _-]/g, '');
      await downloadAsPdf(printRef.current, filename);
    } finally {
      setExporting(false);
    }
  };

  const handleContinue = async () => {
    if (!studyGuide) return;
    setContinuing(true);
    try {
      await studyApi.continueGuide(studyGuide.id);
      onContinue?.();
    } catch {
      // silently fail — user can retry
    } finally {
      setContinuing(false);
    }
  };

  const parsedSuggestionTopics = useMemo(() => {
    if (!studyGuide?.suggestion_topics) return [];
    try {
      const topics = JSON.parse(studyGuide.suggestion_topics) as SuggestionTopic[];
      return [
        ...topics,
        { label: 'Ask Bot', description: 'Ask the AI chatbot any question about this material' },
      ];
    } catch {
      return [];
    }
  }, [studyGuide?.suggestion_topics]);

  const handleGenerateWithContext = () => {
    onGenerate({
      documentType: documentType || undefined,
      studyGoal: studyGoal || undefined,
      studyGoalText: studyGoalText.trim() || undefined,
    });
  };

  return (
    <div className="cm-guide-tab">
      <div className="cm-focus-prompt">
        <div className="cm-focus-prompt-inner">
          <span className="cm-focus-prompt-icon"><FocusIcon /></span>
          <input
            type="text"
            value={focusPrompt}
            onChange={(e) => onFocusPromptChange(e.target.value)}
            placeholder="Focus on a specific topic (e.g., photosynthesis, the Calvin cycle)"
            disabled={generating !== null}
          />
        </div>
      </div>
      {studyGuide ? (
        <div className="cm-tab-card cm-tab-card--guide">
          {!isStreaming && (
            <div className="cm-guide-actions">
              <button className="cm-action-btn" onClick={handlePrint} title="Print">{'\u{1F5A8}\uFE0F'} Print</button>
              <button className="cm-action-btn" onClick={handleDownloadPdf} disabled={exporting} title="Download PDF">{'\u{1F4E5}'} {exporting ? 'Exporting...' : 'PDF'}</button>
              <span className={atLimit ? 'ai-btn-disabled-wrapper' : ''}>
                <button className="cm-action-btn" onClick={() => onGenerate()} disabled={generating !== null || atLimit}>{'\u2728'} Regenerate</button>
                {atLimit && <span className="ai-limit-tooltip">AI limit reached</span>}
              </span>
              <button className="cm-action-btn danger" onClick={() => onDelete(studyGuide)}>{'\u{1F5D1}\uFE0F'} Delete</button>
              {onViewDocument && (
                <button className="cm-action-btn" onClick={onViewDocument} title="View Source Document">{'\u{1F4C4}'} View Source</button>
              )}
              <Link to={`/study/guide/${studyGuide.id}`} state={{ fromMaterial: true }} className="cm-action-btn" title="Open in full page">{'\u{1F5D6}\uFE0F'} Full Page</Link>
            </div>
          )}
          <ContentMetaBar courseName={courseName} createdAt={createdAt || studyGuide.created_at} linkedTasks={linkedTasks} courseId={courseId} />
          <LinkedTasksBanner tasks={linkedTasks} />
          {studyGuide.parent_summary && (
            <ParentSummaryCard summary={studyGuide.parent_summary} />
          )}
          {isStreaming && streamingContent ? (
            <div className="cm-tab-card-body">
              <ContentCard>
                <StreamingMarkdown content={streamingContent} isStreaming={true} />
              </ContentCard>
            </div>
          ) : (
            <>
              {generating === 'study_guide' && !isStreaming && (
                <div className="cm-regen-status">
                  <GenerationSpinner size="md" />
                  <span>Regenerating study guide...</span>
                </div>
              )}
              <div className="cm-tab-card-body" ref={printRef}>
                <ContentCard>
                  <MarkdownErrorBoundary>
                    <Suspense fallback={<div className="content-card-render-loading">Rendering...</div>}>
                      <MarkdownBody content={studyGuide.content} courseContentId={courseContentId} />
                    </Suspense>
                  </MarkdownErrorBoundary>
                </ContentCard>
              </div>
            </>
          )}
          {!isStreaming && parsedSuggestionTopics.length > 0 && (
            <StudyGuideSuggestionChips
              topics={parsedSuggestionTopics}
              onTopicClick={(t) => {
                if (t.label === 'Ask Bot') {
                  const fabBtn = document.querySelector('.speed-dial-fab-btn') as HTMLButtonElement;
                  if (fabBtn) fabBtn.click();
                  return;
                }
                onGenerateChildGuide?.(t.label, 'study_guide');
              }}
              disabled={atLimit}
              generatingTopic={childGuideGenerating}
            />
          )}
          {!isStreaming && studyGuide.is_truncated && (
            <div className="cm-truncated-banner">
              {continuing ? (
                <div className="cm-regen-status">
                  <GenerationSpinner size="md" />
                  <span>Continuing study guide...</span>
                </div>
              ) : (
                <button className="cm-action-btn" onClick={handleContinue} disabled={atLimit}>
                  {'\u2728'} Continue generating
                </button>
              )}
            </div>
          )}
        </div>
      ) : isStreaming && streamingContent ? (
        <div className="cm-tab-card cm-tab-card--guide">
          <div className="cm-tab-card-body">
            <ContentCard>
              <StreamingMarkdown content={streamingContent} isStreaming={true} />
            </ContentCard>
          </div>
        </div>
      ) : generating === 'study_guide' ? (
        <div className="cm-inline-generating">
          {streamStatus === 'connecting' ? (
            <>
              <GenerationSpinner size="lg" />
              <p>Connecting to AI... Please wait.</p>
            </>
          ) : (
            <>
              <GenerationSpinner size="lg" />
              <p>Generating study guide... This may take a moment.</p>
            </>
          )}
        </div>
      ) : (
        <div className="cm-empty-tab cm-empty-tab--with-controls">
          {onFormatSelect && (
            <FormatSelector
              selected="study_guide"
              onSelect={onFormatSelect}
            />
          )}
          <div className="cm-empty-tab-icon"><EmptyGuideIcon /></div>
          <h3>Your document is ready</h3>
          <p>Generate an AI-powered study guide from this material. Customize the options below for the best results.</p>

          {/* Generation controls */}
          {hasSourceContent && (
            <div className="cm-generation-controls">
              <DocumentTypeSelector
                defaultType={documentType || autoDetectedType}
                confidence={autoConfidence}
                onChange={(type) => setDocumentType(type)}
                disabled={generating !== null}
              />

              <StudyGoalSelector
                defaultGoal={studyGoal || null}
                defaultFocusText={studyGoalText || null}
                onChange={(goal, text) => { setStudyGoal(goal); setStudyGoalText(text || ''); }}
                disabled={generating !== null}
              />
            </div>
          )}

          <span className={atLimit ? 'ai-btn-disabled-wrapper' : ''}>
            <button
              className="cm-empty-generate-btn"
              onClick={handleGenerateWithContext}
              disabled={generating !== null || !hasSourceContent || atLimit}
            >
              {'\u2728'} Generate Study Guide
            </button>
            {atLimit && <span className="ai-limit-tooltip">AI limit reached</span>}
          </span>
          {!hasSourceContent && (
            <p className="cm-hint">Add content or upload a document first to generate a study guide.</p>
          )}
        </div>
      )}
    </div>
  );
}
