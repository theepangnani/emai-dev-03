import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import type { StudyGuide } from '../../api/client';
import type { TaskItem } from '../../api/tasks';
import { studyApi } from '../../api/study';
import { classifyDocument } from '../../api/study';
import { parseSSEBuffer } from '../../utils/sseParser';
import { ContentCard, MarkdownBody, MarkdownErrorBoundary } from '../../components/ContentCard';
import { TableOfContents } from '../../components/TableOfContents';
import { CollapsibleMarkdown } from '../../components/CollapsibleMarkdown';
import { FormatSelector, type StudyFormat } from '../../components/study/FormatSelector';
import { GenerationSpinner } from '../../components/GenerationSpinner';
import { StreamingMarkdown } from '../../components/StreamingMarkdown';
import DocumentTypeSelector from '../../components/DocumentTypeSelector';
import StudyGoalSelector from '../../components/StudyGoalSelector';
import { ClassificationBar } from '../../components/study/ClassificationBar';
import MaterialTypeSuggestionChips from '../../components/study/MaterialTypeSuggestionChips';
import ClassificationOverridePanel from '../../components/study/ClassificationOverridePanel';
import { printElement, downloadAsPdf } from '../../utils/exportUtils';
import { LinkedTasksBanner } from './LinkedTasksBanner';
import { ContentMetaBar } from './ContentMetaBar';
import ParentSummaryCard from '../../components/ParentSummaryCard';
import StudyGuideSuggestionChips, { type SuggestionTopic, ASK_BOT_LABEL, FULL_GUIDE_LABEL } from '../../components/StudyGuideSuggestionChips';

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
  onGenerateChildGuide?: (topic: string, guideType: string, extra?: { custom_prompt?: string; max_tokens?: number }) => void | Promise<void>;
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
  const guideContentRef = useRef<HTMLDivElement>(null);
  const continueAbortRef = useRef<AbortController | null>(null);
  const [exporting, setExporting] = useState(false);
  const [continuing, setContinuing] = useState(false);
  const [continuingContent, setContinuingContent] = useState('');
  const [continueError, setContinueError] = useState('');

  // Abort in-flight continue stream on unmount
  useEffect(() => {
    return () => {
      continueAbortRef.current?.abort();
    };
  }, []);

  // Document type & study goal state for empty state generation controls
  const [documentType, setDocumentType] = useState(savedDocumentType || '');
  const [autoDetectedType, setAutoDetectedType] = useState<string | null>(null);
  const [autoConfidence, setAutoConfidence] = useState(0);
  const [isClassifying, setIsClassifying] = useState(false);
  const [showOverride, setShowOverride] = useState(false);
  const [generatingAction, setGeneratingAction] = useState<string | null>(null);
  const [studyGoal, setStudyGoal] = useState(savedStudyGoal || '');
  const [studyGoalText, setStudyGoalText] = useState(savedStudyGoalText || '');

  // Scroll to guide content when a suggestion chip starts generating
  useEffect(() => {
    if (childGuideGenerating && guideContentRef.current) {
      guideContentRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [childGuideGenerating]);

  // Auto-detect document type when empty state is shown
  useEffect(() => {
    if (studyGuide) return; // Only classify when no guide exists
    let cancelled = false;
    const text = (textContent || '').trim();
    const filename = originalFilename || '';
    if (!text && !filename) return;

    setIsClassifying(true);
    classifyDocument(text.slice(0, 2000), filename)
      .then((result) => {
        if (cancelled) return;
        setAutoDetectedType(result.document_type);
        setAutoConfidence(result.confidence);
        if (!documentType) {
          setDocumentType(result.document_type);
        }
      })
      .catch((err) => { console.debug('Auto-detect document type failed:', err?.message || err); })
      .finally(() => { if (!cancelled) setIsClassifying(false); });

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

  const handleContinue = useCallback(async () => {
    if (!studyGuide) return;
    continueAbortRef.current?.abort();
    const controller = new AbortController();
    continueAbortRef.current = controller;

    setContinuing(true);
    setContinuingContent('');
    setContinueError('');

    const token = localStorage.getItem('token') || '';
    const apiBase = import.meta.env.VITE_API_URL ?? '';
    const url = `${apiBase}${studyApi.continueGuideStreamUrl(studyGuide.id)}`;

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        signal: controller.signal,
      });

      if (!response.ok || !response.body) {
        if (controller.signal.aborted) return;
        // Fall back to non-streaming on error
        await studyApi.continueGuide(studyGuide.id);
        onContinue?.();
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let sseBuffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        sseBuffer += decoder.decode(value, { stream: true });
        const { events, remaining } = parseSSEBuffer(sseBuffer);
        sseBuffer = remaining;

        for (const sseEvent of events) {
          try {
            const data = JSON.parse(sseEvent.data);
            if (sseEvent.event === 'chunk') {
              setContinuingContent(prev => prev + (data.text ?? ''));
            } else if (sseEvent.event === 'done') {
              // Stream complete — refresh parent data
              setContinuingContent('');
              onContinue?.();
            } else if (sseEvent.event === 'error') {
              if (controller.signal.aborted) return;
              // Error from backend — fall back to non-streaming
              try {
                await studyApi.continueGuide(studyGuide.id);
                onContinue?.();
              } catch {
                setContinueError('Failed to continue study guide. Please try again.');
              }
              return;
            }
          } catch {
            // Malformed SSE data, skip
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      setContinueError('Failed to continue study guide. Please try again.');
    } finally {
      continueAbortRef.current = null;
      setContinuing(false);
      setContinuingContent('');
    }
  }, [studyGuide, onContinue]);

  const parsedSuggestionTopics = useMemo(() => {
    if (!studyGuide?.suggestion_topics) return [];
    try {
      const topics = JSON.parse(studyGuide.suggestion_topics) as SuggestionTopic[];
      return [
        ...topics,
        { label: FULL_GUIDE_LABEL, description: 'Generate a complete detailed study guide with explanations and examples' },
        { label: ASK_BOT_LABEL, description: 'Ask the AI chatbot any question about this material' },
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

  const handleChipClick = (action: string, templateKey?: string) => {
    setGeneratingAction(templateKey || action);

    // Actions that route to a different tab
    const TAB_ACTIONS: Record<string, StudyFormat> = {
      quiz: 'quiz',
      practice_test: 'quiz',
      flashcards: 'flashcards',
    };
    const targetTab = TAB_ACTIONS[action];
    if (targetTab && onFormatSelect) {
      setGeneratingAction(null);
      onFormatSelect(targetTab);
      return;
    }

    // Remaining actions generate a study guide variant via onGenerate
    onGenerate({
      documentType: documentType || autoDetectedType || undefined,
      studyGoal: studyGoal || undefined,
      studyGoalText: action === 'solve_problems' ? 'problem_solver' : (templateKey || studyGoalText.trim() || undefined),
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
        <div className="cm-tab-card cm-tab-card--guide" ref={guideContentRef}>
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
          {!studyGuide.content && !isStreaming && (
            <div className="cm-tab-card-body" style={{ textAlign: 'center', padding: '2rem' }}>
              <p>Study guide generation was interrupted. Click below to try again.</p>
              <span className={atLimit ? 'ai-btn-disabled-wrapper' : ''}>
                <button className="cm-action-btn" onClick={() => onGenerate()} disabled={generating !== null || atLimit}>{'\u2728'} Regenerate Study Guide</button>
                {atLimit && <span className="ai-limit-tooltip">AI limit reached</span>}
              </span>
            </div>
          )}
          {studyGuide.parent_summary && (
            <ParentSummaryCard summary={studyGuide.parent_summary} />
          )}
          {isStreaming && streamingContent ? (
            <div className="cm-tab-card-body">
              <ContentCard>
                <StreamingMarkdown content={streamingContent} isStreaming={true} />
              </ContentCard>
            </div>
          ) : studyGuide.content ? (
            <>
              {generating === 'study_guide' && !isStreaming && (
                <div className="cm-regen-status">
                  <GenerationSpinner size="md" />
                  <span>Regenerating study guide...</span>
                </div>
              )}
              {studyGuide.parent_guide_id && <TableOfContents content={studyGuide.content} />}
              <div className="cm-tab-card-body" ref={printRef}>
                <ContentCard>
                  {studyGuide.parent_guide_id ? (
                    <CollapsibleMarkdown content={studyGuide.content} guideId={studyGuide.id} courseContentId={courseContentId} />
                  ) : (
                    <MarkdownErrorBoundary>
                      <Suspense fallback={<div className="content-card-render-loading">Rendering...</div>}>
                        <MarkdownBody content={studyGuide.content} courseContentId={courseContentId} />
                      </Suspense>
                    </MarkdownErrorBoundary>
                  )}
                </ContentCard>
              </div>
            </>
          ) : null}
          {!isStreaming && parsedSuggestionTopics.length > 0 && (
            <StudyGuideSuggestionChips
              topics={parsedSuggestionTopics}
              onTopicClick={(t) => {
                if (t.label === ASK_BOT_LABEL) {
                  window.dispatchEvent(new Event('open-help-chat'));
                  return;
                }
                if (t.label === FULL_GUIDE_LABEL) {
                  onGenerateChildGuide?.('Full Study Guide', 'study_guide', {
                    custom_prompt: 'Generate a comprehensive, detailed study guide covering ALL topics from the source material. Include: detailed explanations of each concept, worked examples with step-by-step solutions, practice problems, common mistakes to avoid, and key formulas/rules. This should be thorough enough for a student to study from independently.',
                    max_tokens: 4000,
                  });
                  return;
                }
                onGenerateChildGuide?.(t.label, 'study_guide');
              }}
              disabled={atLimit}
              generatingTopic={childGuideGenerating}
            />
          )}
          {!isStreaming && (
            <div className="cm-truncated-banner">
              {continuing ? (
                <>
                  {continuingContent && (
                    <div className="cm-tab-card-body">
                      <ContentCard>
                        <StreamingMarkdown content={continuingContent} isStreaming={true} />
                      </ContentCard>
                    </div>
                  )}
                  <div className="cm-regen-status">
                    <GenerationSpinner size="md" />
                    <span>Continuing study guide...</span>
                  </div>
                </>
              ) : (
                <>
                  <button className="cm-action-btn" onClick={handleContinue} disabled={atLimit}>
                    {'\u2728'} {studyGuide.is_truncated ? 'Continue generating' : 'Expand this guide'}
                  </button>
                  {continueError && (
                    <p style={{ color: 'var(--color-error, #d32f2f)', fontSize: '0.85rem', margin: '0.5rem 0 0' }}>{continueError}</p>
                  )}
                </>
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

          {/* Auto-detect-and-go: classifying state */}
          {isClassifying && hasSourceContent && (
            <>
              <ClassificationBar detectedSubject={null} confidence={0} childName={null} materialTypeDisplay={null} isClassifying={true} onEditClick={() => {}} />
              <div className="cm-empty-tab-icon"><EmptyGuideIcon /></div>
              <h3>Analyzing your document...</h3>
            </>
          )}

          {/* Auto-detect-and-go: high confidence — show bar + chips directly */}
          {!isClassifying && autoConfidence >= 0.80 && autoDetectedType && hasSourceContent && !showOverride && (
            <>
              <ClassificationBar
                detectedSubject={null}
                confidence={autoConfidence}
                childName={null}
                materialTypeDisplay={autoDetectedType}
                isClassifying={false}
                onEditClick={() => setShowOverride(true)}
              />
              <div className="cm-empty-tab-icon"><EmptyGuideIcon /></div>
              <h3>Ready to go</h3>
              <p>Pick how you want to study this material:</p>
              <MaterialTypeSuggestionChips
                documentType={autoDetectedType || 'custom'}
                onChipClick={handleChipClick}
                disabled={generating !== null || atLimit}
                generatingAction={generatingAction}
                remainingCredits={null}
                atLimit={atLimit}
              />
              {atLimit && <p className="cm-hint">AI limit reached</p>}
            </>
          )}

          {/* Override panel: shown when user clicks "Not right? Change" */}
          {!isClassifying && showOverride && hasSourceContent && (
            <>
              <ClassificationOverridePanel
                documentType={documentType || autoDetectedType || ''}
                studyGoal={studyGoal}
                studyGoalText={studyGoalText}
                autoConfidence={autoConfidence}
                onDocumentTypeChange={(type) => setDocumentType(type)}
                onStudyGoalChange={(goal, text) => { setStudyGoal(goal); setStudyGoalText(text || ''); }}
                onGenerate={handleGenerateWithContext}
                onClose={() => setShowOverride(false)}
                disabled={generating !== null}
                atLimit={atLimit}
                hasSourceContent={hasSourceContent}
              />
            </>
          )}

          {/* Fallback: low confidence or no detection — show original selectors + generate button */}
          {!isClassifying && (autoConfidence < 0.80 || !autoDetectedType) && !showOverride && (
            <>
              <div className="cm-empty-tab-icon"><EmptyGuideIcon /></div>
              <h3>Your document is ready</h3>
              <p>Generate an AI-powered study guide from this material. Customize the options below for the best results.</p>

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
            </>
          )}
        </div>
      )}
    </div>
  );
}
