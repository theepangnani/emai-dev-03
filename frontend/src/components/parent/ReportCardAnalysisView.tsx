import { useState } from 'react';
import type {
  FullAnalysis,
  SchoolReportCard,
} from '../../api/schoolReportCards';
import './ReportCardAnalysisView.css';

interface ReportCardAnalysisViewProps {
  analysis: FullAnalysis;
  reportCard: SchoolReportCard;
  onClose?: () => void;
}

const ALL_SECTIONS = [
  'teacher-feedback',
  'grade-analysis',
  'learning-skills',
  'improvement-areas',
  'parent-tips',
  'overall-summary',
];

function gradeClass(grade: string | null, median: string | null): string {
  if (grade == null || median == null) return '';
  const g = parseFloat(grade);
  const m = parseFloat(median);
  if (isNaN(g) || isNaN(m)) return '';
  const diff = g - m;
  if (diff > m * 0.05) return 'rca-grade-above';
  if (diff >= -(m * 0.05)) return 'rca-grade-near';
  return 'rca-grade-below';
}

export function ReportCardAnalysisView({ analysis, reportCard, onClose }: ReportCardAnalysisViewProps) {
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set(ALL_SECTIONS));
  const [expandedComments, setExpandedComments] = useState<Set<number>>(() => new Set());

  const toggle = (section: string) => {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(section)) {
        next.delete(section);
      } else {
        next.add(section);
      }
      return next;
    });
  };

  const toggleComment = (index: number) => {
    setExpandedComments(prev => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  const isOpen = (section: string) => expanded.has(section);

  const renderSectionHeader = (section: string, icon: string, title: string) => (
    <button
      className="rca-section-header"
      onClick={() => toggle(section)}
      type="button"
      aria-expanded={isOpen(section)}
    >
      <span className="rca-section-icon" aria-hidden="true">{icon}</span>
      <span className="rca-section-title">{title}</span>
      <span className="rca-section-toggle">{isOpen(section) ? '\u25B2' : '\u25BC'}</span>
    </button>
  );

  return (
    <div className="rca-container">
      <div className="rca-header">
        <div>
          <h2>Report Card Analysis</h2>
          <p className="rca-header-meta">
            {reportCard.term} &middot; {reportCard.term} &middot; {reportCard.school_year}
          </p>
        </div>
        {onClose && (
          <button className="rca-close-btn" onClick={onClose} type="button">
            Close
          </button>
        )}
      </div>

      <div className="rca-sections">
        {/* 1. Teacher Feedback Summary */}
        <div className={`rca-section${isOpen('teacher-feedback') ? ' rca-section-open' : ''}`}>
          {renderSectionHeader('teacher-feedback', '\uD83D\uDCDD', 'Teacher Feedback Summary')}
          {isOpen('teacher-feedback') && (
            <div className="rca-section-body">
              <p className="rca-feedback-text">{analysis.teacher_feedback_summary}</p>
            </div>
          )}
        </div>

        {/* 2. Grade Analysis Table */}
        <div className={`rca-section${isOpen('grade-analysis') ? ' rca-section-open' : ''}`}>
          {renderSectionHeader('grade-analysis', '\uD83D\uDCCA', 'Grade Analysis')}
          {isOpen('grade-analysis') && (
            <div className="rca-section-body">
              {analysis.grade_analysis.length > 0 ? (
                <table className="rca-grade-table">
                  <thead>
                    <tr>
                      <th>Subject</th>
                      <th>Grade</th>
                      <th>Median</th>
                      <th>Level</th>
                      <th>Feedback</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analysis.grade_analysis.map((item, i) => (
                      <tr key={i}>
                        <td>{item.subject}</td>
                        <td>
                          {item.grade != null ? (
                            <span className={`rca-grade-cell ${gradeClass(item.grade, item.median)}`}>
                              {item.grade}%
                            </span>
                          ) : (
                            '\u2014'
                          )}
                        </td>
                        <td>{item.median != null ? `${item.median}%` : '\u2014'}</td>
                        <td>{item.level ?? '\u2014'}</td>
                        <td>
                          {item.feedback ?? '\u2014'}
                          {item.teacher_comment && (
                            <div>
                              <button
                                className="rca-teacher-comment-toggle"
                                onClick={() => toggleComment(i)}
                                type="button"
                              >
                                {expandedComments.has(i) ? 'Hide comment' : 'Show comment'}
                              </button>
                              {expandedComments.has(i) && (
                                <p className="rca-teacher-comment">{item.teacher_comment}</p>
                              )}
                            </div>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="rca-no-data">No grade data available for this report card</p>
              )}
            </div>
          )}
        </div>

        {/* 3. Learning Skills Assessment */}
        <div className={`rca-section${isOpen('learning-skills') ? ' rca-section-open' : ''}`}>
          {renderSectionHeader('learning-skills', '\uD83C\uDFAF', 'Learning Skills Assessment')}
          {isOpen('learning-skills') && (
            <div className="rca-section-body">
              <div className="rca-skills-grid">
                {analysis.learning_skills.ratings.map((r, i) => (
                  <div className="rca-skill-item" key={i}>
                    <span className="rca-skill-name">{r.skill}</span>
                    <span className={`rca-skill-badge rca-skill-${r.rating}`}>{r.rating}</span>
                  </div>
                ))}
              </div>
              {analysis.learning_skills.summary && (
                <p className="rca-skills-summary">{analysis.learning_skills.summary}</p>
              )}
            </div>
          )}
        </div>

        {/* 4. Improvement Areas */}
        <div className={`rca-section${isOpen('improvement-areas') ? ' rca-section-open' : ''}`}>
          {renderSectionHeader('improvement-areas', '\uD83D\uDCC8', 'Improvement Areas')}
          {isOpen('improvement-areas') && (
            <div className="rca-section-body">
              {analysis.improvement_areas.length > 0 ? (
                <div className="rca-improvement-list">
                  {analysis.improvement_areas.map((item, i) => (
                    <div className={`rca-improvement-item rca-priority-${item.priority}`} key={i}>
                      <span className="rca-priority-dot" aria-hidden="true" />
                      <div className="rca-improvement-content">
                        <p className="rca-improvement-area">{item.area}</p>
                        <p className="rca-improvement-detail">{item.detail}</p>
                      </div>
                      <span className={`rca-priority-badge rca-priority-badge-${item.priority}`}>
                        {item.priority}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="rca-no-data">No specific improvement areas identified</p>
              )}
            </div>
          )}
        </div>

        {/* 5. Parent Tips */}
        <div className={`rca-section${isOpen('parent-tips') ? ' rca-section-open' : ''}`}>
          {renderSectionHeader('parent-tips', '\uD83D\uDCA1', 'Parent Tips')}
          {isOpen('parent-tips') && (
            <div className="rca-section-body">
              {analysis.parent_tips.length > 0 ? (
                <div className="rca-tips-list">
                  {analysis.parent_tips.map((tip, i) => (
                    <div className="rca-tip-item" key={i}>
                      <span className="rca-tip-icon" aria-hidden="true">{'\uD83D\uDCA1'}</span>
                      <div className="rca-tip-content">
                        <p className="rca-tip-text">{tip.tip}</p>
                        {tip.related_subject && (
                          <span className="rca-tip-subject">{tip.related_subject}</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="rca-no-data">No parent tips available</p>
              )}
            </div>
          )}
        </div>

        {/* 6. Overall Summary */}
        <div className={`rca-section${isOpen('overall-summary') ? ' rca-section-open' : ''}`}>
          {renderSectionHeader('overall-summary', '\uD83D\uDCCB', 'Overall Summary')}
          {isOpen('overall-summary') && (
            <div className="rca-section-body">
              <p className="rca-overall-text">{analysis.overall_summary}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
