import { useState } from 'react';
import type { Worksheet } from '../../api/study';
import type { StudyGuide } from '../../api/client';
import { WorksheetContent } from '../../components/study/WorksheetContent';
import { GenerationSpinner } from '../../components/GenerationSpinner';
type TemplateKey = 'worksheet_general' | 'worksheet_math_word_problems' | 'worksheet_english' | 'worksheet_french';
type Difficulty = 'below_grade' | 'grade_level' | 'above_grade';

const TEMPLATES: { key: TemplateKey; label: string }[] = [
  { key: 'worksheet_general', label: 'General' },
  { key: 'worksheet_math_word_problems', label: 'Math Word Problems' },
  { key: 'worksheet_english', label: 'English' },
  { key: 'worksheet_french', label: 'French' },
];

const DIFFICULTIES: { key: Difficulty; label: string }[] = [
  { key: 'below_grade', label: 'Easier' },
  { key: 'grade_level', label: 'Grade Level' },
  { key: 'above_grade', label: 'Challenging' },
];

const NUM_QUESTIONS_OPTIONS = [5, 10, 15, 20];

interface WorksheetsTabProps {
  worksheet: Worksheet | undefined;
  courseContentId: number;
  hasSourceContent: boolean;
  atLimit: boolean;
  generating: string | null;
  onGenerate: (opts: { template_key: string; difficulty: string; num_questions: number }) => void;
  onDelete: (guide: StudyGuide) => void;
  onViewDocument: () => void;
  courseName?: string | null;
  createdAt?: string | null;
}

function EmptyWorksheetIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="4" y="2" width="16" height="20" rx="2" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M8 7h8M8 11h8M8 15h5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
    </svg>
  );
}

export function WorksheetsTab({
  worksheet,
  hasSourceContent,
  generating,
  atLimit = false,
  onGenerate,
  onDelete,
  onViewDocument,
}: WorksheetsTabProps) {
  const [templateKey, setTemplateKey] = useState<TemplateKey>('worksheet_general');
  const [difficulty, setDifficulty] = useState<Difficulty>('grade_level');
  const [numQuestions, setNumQuestions] = useState(10);

  const handleGenerate = () => {
    onGenerate({ template_key: templateKey, difficulty, num_questions: numQuestions });
  };

  return (
    <div className="cm-quiz-tab">
      {/* Options bar */}
      <div className="cm-focus-prompt">
        <div className="cm-focus-prompt-inner" style={{ gap: '0.75rem', flexWrap: 'wrap' }}>
          <label className="cm-difficulty-label" style={{ whiteSpace: 'nowrap' }}>Type:</label>
          <select
            value={templateKey}
            onChange={(e) => setTemplateKey(e.target.value as TemplateKey)}
            disabled={generating !== null}
            className="cm-worksheet-select"
          >
            {TEMPLATES.map(t => (
              <option key={t.key} value={t.key}>{t.label}</option>
            ))}
          </select>

          <label className="cm-difficulty-label" style={{ whiteSpace: 'nowrap', marginLeft: '0.5rem' }}>Questions:</label>
          <select
            value={numQuestions}
            onChange={(e) => setNumQuestions(Number(e.target.value))}
            disabled={generating !== null}
            className="cm-worksheet-select"
          >
            {NUM_QUESTIONS_OPTIONS.map(n => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </div>
        <div className="cm-difficulty-selector">
          <span className="cm-difficulty-label">Difficulty:</span>
          <div className="cm-difficulty-toggle">
            {DIFFICULTIES.map(level => (
              <button
                key={level.key}
                className={`cm-difficulty-btn${difficulty === level.key ? ' active' : ''}`}
                onClick={() => setDifficulty(level.key)}
                disabled={generating !== null}
              >
                {level.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {worksheet ? (
        <div className="cm-tab-card">
          <div className="cm-guide-actions">
            <span className={atLimit ? 'ai-btn-disabled-wrapper' : ''}>
              <button className="cm-action-btn" onClick={handleGenerate} disabled={generating !== null || atLimit}>
                {generating === 'worksheet' ? <><GenerationSpinner size="sm" /> Regenerating...</> : <>{'\u2728'} Regenerate</>}
              </button>
              {atLimit && <span className="ai-limit-tooltip">AI limit reached</span>}
            </span>
            <button className="cm-action-btn danger" onClick={() => onDelete(worksheet as unknown as StudyGuide)}>{'\u{1F5D1}\uFE0F'} Delete</button>
            <button className="cm-action-btn" onClick={onViewDocument} title="View Source Document">{'\u{1F4C4}'} View Source</button>
          </div>
          {generating === 'worksheet' && (
            <div className="cm-regen-status">
              <GenerationSpinner size="md" />
              <span>Regenerating worksheet...</span>
            </div>
          )}
          <WorksheetContent worksheet={worksheet} />
        </div>
      ) : generating === 'worksheet' ? (
        <div className="cm-inline-generating">
          <GenerationSpinner size="lg" />
          <p>Generating worksheet... This may take a moment.</p>
        </div>
      ) : (
        <div className="cm-empty-tab">
          <div className="cm-empty-tab-icon"><EmptyWorksheetIcon /></div>
          <h3>Generate a printable worksheet</h3>
          <p>Create practice worksheets with questions and an answer key from this material. Choose a type, difficulty, and number of questions above.</p>
          <span className={atLimit ? 'ai-btn-disabled-wrapper' : ''}>
            <button
              className="cm-empty-generate-btn"
              onClick={handleGenerate}
              disabled={generating !== null || !hasSourceContent || atLimit}
            >
              {'\u2728'} Generate Worksheet
            </button>
            {atLimit && <span className="ai-limit-tooltip">AI limit reached</span>}
          </span>
          {!hasSourceContent && (
            <p className="cm-hint">Upload a source document first to generate worksheets.</p>
          )}
        </div>
      )}
    </div>
  );
}
