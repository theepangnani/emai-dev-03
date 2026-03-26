import { Suspense, useRef, useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import type { StudyGuide } from '../../api/client';
import type { TaskItem } from '../../api/tasks';
import { studyApi } from '../../api/study';
import { ContentCard, MarkdownBody, MarkdownErrorBoundary } from '../../components/ContentCard';
import { FormatSelector, type StudyFormat } from '../../components/study/FormatSelector';
import { GenerationSpinner } from '../../components/GenerationSpinner';
import { StreamingMarkdown } from '../../components/StreamingMarkdown';
import { printElement, downloadAsPdf } from '../../utils/exportUtils';
import { LinkedTasksBanner } from './LinkedTasksBanner';
import ParentSummaryCard from '../../components/ParentSummaryCard';

interface StudyGuideTabProps {
  studyGuide: StudyGuide | undefined;
  generating: string | null;
  focusPrompt: string;
  onFocusPromptChange: (value: string) => void;
  onGenerate: () => void;
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
}: StudyGuideTabProps) {
  const printRef = useRef<HTMLDivElement>(null);
  const [exporting, setExporting] = useState(false);
  const [continuing, setContinuing] = useState(false);
  const [classPopover, setClassPopover] = useState(false);
  const [tasksPopover, setTasksPopover] = useState(false);
  const classPopoverRef = useRef<HTMLSpanElement>(null);
  const tasksPopoverRef = useRef<HTMLSpanElement>(null);

  const closePopovers = useCallback(() => {
    setClassPopover(false);
    setTasksPopover(false);
  }, []);

  useEffect(() => {
    if (!classPopover && !tasksPopover) return;
    const handleClick = (e: MouseEvent) => {
      if (classPopover && classPopoverRef.current && !classPopoverRef.current.contains(e.target as Node)) {
        setClassPopover(false);
      }
      if (tasksPopover && tasksPopoverRef.current && !tasksPopoverRef.current.contains(e.target as Node)) {
        setTasksPopover(false);
      }
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closePopovers();
    };
    document.addEventListener('mousedown', handleClick);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handleClick);
      document.removeEventListener('keydown', handleKey);
    };
  }, [classPopover, tasksPopover, closePopovers]);

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
                <button className="cm-action-btn" onClick={onGenerate} disabled={generating !== null || atLimit}>{'\u2728'} Regenerate</button>
                {atLimit && <span className="ai-limit-tooltip">AI limit reached</span>}
              </span>
              <button className="cm-action-btn danger" onClick={() => onDelete(studyGuide)}>{'\u{1F5D1}\uFE0F'} Delete</button>
              {onViewDocument && (
                <button className="cm-action-btn" onClick={onViewDocument} title="View Source Document">{'\u{1F4C4}'} View Source</button>
              )}
              <Link to={`/study/guide/${studyGuide.id}`} state={{ fromMaterial: true }} className="cm-action-btn" title="Open in full page">{'\u{1F5D6}\uFE0F'} Full Page</Link>
            </div>
          )}
          <div className="cm-guide-meta">
            {courseName && (
              <span className="cm-guide-meta-item cm-guide-meta-item--popover-anchor" ref={classPopoverRef}>
                <button
                  type="button"
                  className="cm-guide-meta-link"
                  onClick={() => { setClassPopover(!classPopover); setTasksPopover(false); }}
                  aria-expanded={classPopover}
                >
                  <span className="cm-guide-meta-label">Class:</span> {courseName}
                </button>
                {classPopover && (
                  <div className="cm-meta-popover">
                    <div className="cm-meta-popover-header">Class Details</div>
                    <div className="cm-meta-popover-row">
                      <span className="cm-meta-popover-label">Name</span>
                      <span>{courseName}</span>
                    </div>
                    {courseId && (
                      <div className="cm-meta-popover-actions">
                        <Link to={`/courses/${courseId}`} className="cm-meta-popover-btn" onClick={closePopovers}>
                          View Course
                        </Link>
                      </div>
                    )}
                  </div>
                )}
              </span>
            )}
            {(createdAt || studyGuide.created_at) && (
              <span className="cm-guide-meta-item">
                <span className="cm-guide-meta-label">Created:</span>{' '}
                {new Date(createdAt || studyGuide.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
              </span>
            )}
            <span className={`cm-guide-meta-item cm-guide-meta-item--popover-anchor${linkedTasks.length === 0 ? ' cm-guide-meta-item--muted' : ''}`} ref={tasksPopoverRef}>
              <button
                type="button"
                className="cm-guide-meta-link"
                onClick={() => { setTasksPopover(!tasksPopover); setClassPopover(false); }}
                aria-expanded={tasksPopover}
              >
                <span className="cm-guide-meta-label">Tasks:</span>{' '}
                {linkedTasks.length > 0 ? `${linkedTasks.length} linked` : 'No tasks linked'}
              </button>
              {tasksPopover && (
                <div className="cm-meta-popover cm-meta-popover--tasks">
                  <div className="cm-meta-popover-header">Linked Tasks</div>
                  {linkedTasks.length > 0 ? (
                    <div className="cm-meta-popover-task-list">
                      {linkedTasks.map(task => {
                        const dateOnly = task.due_date?.substring(0, 10);
                        const d = dateOnly ? new Date(dateOnly + 'T00:00:00') : null;
                        const isOverdue = d ? d < new Date() && !task.is_completed : false;
                        return (
                          <Link
                            key={task.id}
                            to={`/tasks/${task.id}`}
                            className="cm-meta-popover-task"
                            onClick={closePopovers}
                          >
                            <span className={`cm-meta-popover-task-status${task.is_completed ? ' done' : ''}`}>
                              {task.is_completed ? '\u2713' : '\u25CB'}
                            </span>
                            <span className="cm-meta-popover-task-title">{task.title}</span>
                            {d && (
                              <span className={`cm-meta-popover-task-due${isOverdue ? ' overdue' : ''}`}>
                                {d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                              </span>
                            )}
                          </Link>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="cm-meta-popover-empty">No tasks are linked to this study guide.</div>
                  )}
                </div>
              )}
            </span>
          </div>
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
        <div className="cm-empty-tab">
          {onFormatSelect && (
            <FormatSelector
              selected="study_guide"
              onSelect={onFormatSelect}
            />
          )}
          <div className="cm-empty-tab-icon"><EmptyGuideIcon /></div>
          <h3>No study guide yet</h3>
          <p>Generate an AI-powered study guide from this material to help with studying and review.</p>
          <span className={atLimit ? 'ai-btn-disabled-wrapper' : ''}>
            <button
              className="cm-empty-generate-btn"
              onClick={onGenerate}
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
