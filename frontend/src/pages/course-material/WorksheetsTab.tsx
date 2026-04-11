interface WorksheetsTabProps {
  courseContentId: number;
  hasSourceContent: boolean;
  atLimit: boolean;
  generating: string | null;
  onViewDocument: () => void;
}

export function WorksheetsTab({
  hasSourceContent,
  generating,
  onViewDocument,
}: WorksheetsTabProps) {
  return (
    <div className="cm-tab-card">
      <div className="cm-tab-card-body">
        <div className="cm-empty-tab">
          <div className="cm-empty-tab-icon">
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none" aria-hidden="true">
              <rect x="6" y="4" width="36" height="40" rx="4" stroke="currentColor" strokeWidth="2" opacity="0.3"/>
              <path d="M14 16h20M14 22h20M14 28h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" opacity="0.3"/>
              <rect x="12" y="34" width="8" height="4" rx="1" stroke="currentColor" strokeWidth="1.5" opacity="0.3"/>
              <rect x="24" y="34" width="8" height="4" rx="1" stroke="currentColor" strokeWidth="1.5" opacity="0.3"/>
            </svg>
          </div>
          <h3>Worksheets</h3>
          <p className="cm-empty-tab-desc">
            {!hasSourceContent
              ? 'Upload a source document first to generate worksheets.'
              : generating
                ? 'Generation in progress...'
                : 'No worksheets generated yet. Worksheet generation is coming soon.'}
          </p>
          {!hasSourceContent && (
            <button className="cm-empty-tab-btn" onClick={onViewDocument}>
              View Document
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
