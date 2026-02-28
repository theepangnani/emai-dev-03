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
        <input
          type="text"
          value={focusPrompt}
          onChange={(e) => onFocusPromptChange(e.target.value)}
          placeholder="Focus on... (e.g., photosynthesis and the Calvin cycle)"
          disabled={generating !== null}
        />
      </div>
      {studyGuide ? (
        <>
          <div className="cm-guide-actions">
            <button className="cm-action-btn" onClick={handlePrint} title="Print">{'\u{1F5A8}\uFE0F'} Print</button>
            <button className="cm-action-btn" onClick={handleDownloadPdf} disabled={exporting} title="Download PDF">{'\u{1F4E5}'} {exporting ? 'Exporting...' : 'Download PDF'}</button>
            <button className="cm-action-btn" onClick={onGenerate} disabled={generating !== null}>{generating === 'study_guide' ? <><span className="cm-inline-spinner" /> Regenerating...</> : <>{'\u2728'} Regenerate</>}</button>
            <button className="cm-action-btn danger" onClick={() => onDelete(studyGuide)}>{'\u{1F5D1}\uFE0F'} Delete</button>
          </div>
          <LinkedTasksBanner tasks={linkedTasks} />
          {generating === 'study_guide' && (
            <div className="cm-regen-status">
              <div className="cm-inline-spinner" />
              <span>Regenerating study guide...</span>
            </div>
          )}
          <div ref={printRef}>
            <ContentCard>
              <Suspense fallback={<div className="content-card-render-loading">Rendering...</div>}>
                <MarkdownBody content={studyGuide.content} />
              </Suspense>
            </ContentCard>
          </div>
        </>
      ) : generating === 'study_guide' ? (
        <div className="cm-inline-generating">
          <div className="cm-inline-spinner" />
          <p>Generating study guide... This may take a moment.</p>
        </div>
      ) : (
        <div className="cm-empty-tab">
          <p>No study guide generated yet.</p>
          <button
            className="generate-btn"
            onClick={onGenerate}
            disabled={generating !== null || !hasSourceContent}
          >
            Generate Study Guide
          </button>
          {!hasSourceContent && (
            <p className="cm-hint">Add content or upload a document first to generate a study guide.</p>
          )}
        </div>
      )}
    </div>
  );
}
