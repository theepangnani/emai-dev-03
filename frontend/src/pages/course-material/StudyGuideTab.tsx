import { Suspense, useRef, useState } from 'react';
import type { StudyGuide } from '../../api/client';
import type { TaskItem } from '../../api/tasks';
import { ContentCard, MarkdownBody } from '../../components/ContentCard';
import { printElement, downloadAsPdf } from '../../utils/exportUtils';
import { LinkedTasksBanner } from './LinkedTasksBanner';

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
}: StudyGuideTabProps) {
  const printRef = useRef<HTMLDivElement>(null);
  const [exporting, setExporting] = useState(false);

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
          <div className="cm-guide-actions">
            <button className="cm-action-btn" onClick={handlePrint} title="Print">{'\u{1F5A8}\uFE0F'} Print</button>
            <button className="cm-action-btn" onClick={handleDownloadPdf} disabled={exporting} title="Download PDF">{'\u{1F4E5}'} {exporting ? 'Exporting...' : 'PDF'}</button>
            <span className={atLimit ? 'ai-btn-disabled-wrapper' : ''}>
              <button className="cm-action-btn" onClick={onGenerate} disabled={generating !== null || atLimit}>{'\u2728'} Regenerate</button>
              {atLimit && <span className="ai-limit-tooltip">AI limit reached</span>}
            </span>
            <button className="cm-action-btn danger" onClick={() => onDelete(studyGuide)}>{'\u{1F5D1}\uFE0F'} Delete</button>
          </div>
          <LinkedTasksBanner tasks={linkedTasks} />
          {generating === 'study_guide' && (
            <div className="cm-regen-status">
              <div className="cm-inline-spinner" />
              <span>Regenerating study guide...</span>
            </div>
          )}
          <div className="cm-tab-card-body" ref={printRef}>
            <ContentCard>
              <Suspense fallback={<div className="content-card-render-loading">Rendering...</div>}>
                <MarkdownBody content={studyGuide.content} courseContentId={courseContentId} />
              </Suspense>
            </ContentCard>
          </div>
        </div>
      ) : generating === 'study_guide' ? (
        <div className="cm-inline-generating">
          <div className="cm-inline-spinner" />
          <p>Generating study guide... This may take a moment.</p>
        </div>
      ) : (
        <div className="cm-empty-tab">
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
