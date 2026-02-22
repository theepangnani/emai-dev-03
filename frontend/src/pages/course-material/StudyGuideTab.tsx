import { Suspense } from 'react';
import type { StudyGuide } from '../../api/client';
import { ContentCard, MarkdownBody } from '../../components/ContentCard';

interface StudyGuideTabProps {
  studyGuide: StudyGuide | undefined;
  generating: string | null;
  focusPrompt: string;
  onFocusPromptChange: (value: string) => void;
  onGenerate: () => void;
  onDelete: (guide: StudyGuide) => void;
  hasSourceContent: boolean;
}

export function StudyGuideTab({
  studyGuide,
  generating,
  focusPrompt,
  onFocusPromptChange,
  onGenerate,
  onDelete,
  hasSourceContent,
}: StudyGuideTabProps) {
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
            <button className="cm-action-btn" onClick={() => window.print()} title="Print">{'\u{1F5A8}\uFE0F'} Print</button>
            <button className="cm-action-btn" onClick={onGenerate} disabled={generating !== null}>{'\u2728'} Regenerate</button>
            <button className="cm-action-btn danger" onClick={() => onDelete(studyGuide)}>{'\u{1F5D1}\uFE0F'} Delete</button>
          </div>
          <ContentCard>
            <Suspense fallback={<div className="content-card-render-loading">Rendering...</div>}>
              <MarkdownBody content={studyGuide.content} />
            </Suspense>
          </ContentCard>
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
