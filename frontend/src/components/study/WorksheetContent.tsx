import { Suspense, useState, useCallback } from 'react';
import { MarkdownBody, MarkdownErrorBoundary } from '../ContentCard';
import type { Worksheet } from '../../api/study';
import './WorksheetContent.css';

const DIFFICULTY_LABELS: Record<string, string> = {
  below_grade: 'Below Grade',
  grade_level: 'Grade Level',
  above_grade: 'Above Grade',
};

const TEMPLATE_LABELS: Record<string, string> = {
  worksheet_general: 'General',
  worksheet_math_word_problems: 'Math Word Problems',
  worksheet_english: 'English',
  worksheet_french: 'French',
};

interface WorksheetContentProps {
  worksheet: Worksheet;
}

export function WorksheetContent({ worksheet }: WorksheetContentProps) {
  const [showAnswerKey, setShowAnswerKey] = useState(false);

  const handlePrint = useCallback(() => {
    window.print();
  }, []);

  const handlePdf = useCallback(async () => {
    try {
      const { downloadAsPdf } = await import('../../utils/exportUtils');
      const el = document.querySelector('.worksheet-body');
      if (el instanceof HTMLElement) {
        await downloadAsPdf(el, worksheet.title || 'worksheet');
      }
    } catch {
      // Fallback to print
      window.print();
    }
  }, [worksheet.title]);

  const createdDate = worksheet.created_at
    ? new Date(worksheet.created_at).toLocaleDateString()
    : '';

  return (
    <div className="worksheet-content">
      <div className="worksheet-meta">
        {worksheet.num_questions != null && (
          <span className="worksheet-meta-item">
            {worksheet.num_questions} questions
          </span>
        )}
        {worksheet.difficulty && (
          <span className="worksheet-meta-item">
            {DIFFICULTY_LABELS[worksheet.difficulty] || worksheet.difficulty}
          </span>
        )}
        {worksheet.template_key && (
          <span className="worksheet-meta-item">
            {TEMPLATE_LABELS[worksheet.template_key] || worksheet.template_key}
          </span>
        )}
        {createdDate && (
          <span className="worksheet-meta-item">{createdDate}</span>
        )}
      </div>

      <div className="worksheet-actions">
        <button type="button" onClick={handlePrint}>
          Print
        </button>
        <button type="button" onClick={handlePdf}>
          PDF
        </button>
      </div>

      <div className="worksheet-body">
        <Suspense fallback={<p>Loading...</p>}>
          <MarkdownErrorBoundary>
            <MarkdownBody
              content={worksheet.content}
              courseContentId={worksheet.course_content_id ?? undefined}
            />
          </MarkdownErrorBoundary>
        </Suspense>
      </div>

      {worksheet.answer_key_markdown && (
        <div className="worksheet-answer-key">
          <button
            type="button"
            className="worksheet-answer-key-toggle"
            onClick={() => setShowAnswerKey((v) => !v)}
          >
            {showAnswerKey ? 'Hide' : 'View'} Answer Key
          </button>
          {showAnswerKey && (
            <div className="worksheet-answer-key-body">
              <Suspense fallback={<p>Loading...</p>}>
                <MarkdownErrorBoundary>
                  <MarkdownBody
                    content={worksheet.answer_key_markdown}
                    courseContentId={worksheet.course_content_id ?? undefined}
                  />
                </MarkdownErrorBoundary>
              </Suspense>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
