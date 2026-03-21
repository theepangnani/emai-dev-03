import { useState } from 'react';
import { BugReportModal } from './BugReportModal';
import './ReportBugLink.css';

interface ReportBugLinkProps {
  errorMessage?: string;
  className?: string;
}

export function ReportBugLink({ errorMessage, className }: ReportBugLinkProps) {
  const [showModal, setShowModal] = useState(false);

  return (
    <>
      <button
        type="button"
        className={`report-bug-link ${className || ''}`}
        onClick={() => setShowModal(true)}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M8 2l1.88 1.88M14.12 3.88L16 2M9 7.13v-1a3.003 3.003 0 116 0v1" />
          <path d="M12 20c-3.3 0-6-2.7-6-6v-3a4 4 0 014-4h4a4 4 0 014 4v3c0 3.3-2.7 6-6 6" />
          <path d="M12 20v2M6 13H2M22 13h-4M6 17H3.5M20.5 17H18M6 9H4M20 9h-2" />
        </svg>
        Report this issue
      </button>
      <BugReportModal
        open={showModal}
        onClose={() => setShowModal(false)}
        prefillDescription={errorMessage ? `Error: ${errorMessage}` : undefined}
        prefillPageUrl={window.location.href}
      />
    </>
  );
}
