import { Suspense, useRef, useState } from 'react';
import type { BriefingNote } from '../../api/client';
import { ContentCard, MarkdownBody } from '../../components/ContentCard';
import { printElement, downloadAsPdf } from '../../utils/exportUtils';

interface BriefingTabProps {
  briefingNote: BriefingNote | undefined;
  generating: boolean;
  onGenerate: () => void;
  onDelete: (note: BriefingNote) => void;
  hasSourceContent: boolean;
  atLimit?: boolean;
  studentName?: string;
  courseContentId?: number;
}

function BriefingIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M17 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V5a2 2 0 00-2-2z" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M9 7h6M9 11h6M9 15h4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
      <circle cx="18" cy="5" r="3" fill="var(--color-accent-strong, #2a9fa8)" stroke="none"/>
    </svg>
  );
}

export function BriefingTab({
  briefingNote,
  generating,
  onGenerate,
  onDelete,
  hasSourceContent,
  atLimit = false,
  studentName,
  courseContentId,
}: BriefingTabProps) {
  const printRef = useRef<HTMLDivElement>(null);
  const [exporting, setExporting] = useState(false);

  const handlePrint = () => {
    if (printRef.current) printElement(printRef.current, briefingNote?.title || 'Parent Briefing');
  };

  const handleDownloadPdf = async () => {
    if (!printRef.current) return;
    setExporting(true);
    try {
      const filename = (briefingNote?.title || 'Parent Briefing').replace(/[^a-zA-Z0-9 _-]/g, '');
      await downloadAsPdf(printRef.current, filename);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="cm-guide-tab">
      {briefingNote ? (
        <div className="cm-tab-card cm-tab-card--guide">
          <div className="cm-guide-actions">
            <button className="cm-action-btn" onClick={handlePrint} title="Print">Print</button>
            <button className="cm-action-btn" onClick={handleDownloadPdf} disabled={exporting} title="Download PDF">{exporting ? 'Exporting...' : 'PDF'}</button>
            <span className={atLimit ? 'ai-btn-disabled-wrapper' : ''}>
              <button className="cm-action-btn" onClick={onGenerate} disabled={generating || atLimit}>Regenerate</button>
              {atLimit && <span className="ai-limit-tooltip">AI limit reached</span>}
            </span>
            <button className="cm-action-btn danger" onClick={() => onDelete(briefingNote)}>Delete</button>
          </div>
          {generating && (
            <div className="cm-regen-status">
              <div className="cm-inline-spinner" />
              <span>Regenerating parent briefing...</span>
            </div>
          )}
          <div className="cm-tab-card-body" ref={printRef}>
            <ContentCard>
              <Suspense fallback={<div className="content-card-render-loading">Rendering...</div>}>
                <MarkdownBody content={briefingNote.content} courseContentId={courseContentId} />
              </Suspense>
            </ContentCard>
          </div>
        </div>
      ) : generating ? (
        <div className="cm-inline-generating">
          <div className="cm-inline-spinner" />
          <p>Generating parent briefing{studentName ? ` for ${studentName}'s material` : ''}... This may take a moment.</p>
        </div>
      ) : (
        <div className="cm-empty-tab">
          <div className="cm-empty-tab-icon"><BriefingIcon /></div>
          <h3>Parent Briefing</h3>
          <p>
            Get an AI-generated summary written just for you as a parent.
            Understand what {studentName || 'your child'} is learning and how you can help at home.
          </p>
          <span className={atLimit ? 'ai-btn-disabled-wrapper' : ''}>
            <button
              className="cm-empty-generate-btn"
              onClick={onGenerate}
              disabled={generating || !hasSourceContent || atLimit}
            >
              Generate Parent Briefing
            </button>
            {atLimit && <span className="ai-limit-tooltip">AI limit reached</span>}
          </span>
          {!hasSourceContent && (
            <p className="cm-empty-hint">No source content available to generate a briefing from.</p>
          )}
        </div>
      )}
    </div>
  );
}
