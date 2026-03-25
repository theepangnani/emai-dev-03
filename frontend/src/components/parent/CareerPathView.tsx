import type { CareerPathAnalysis, GradeTrend } from '../../api/schoolReportCards';
import './CareerPathView.css';

interface CareerPathViewProps {
  careerPath: CareerPathAnalysis;
  onClose?: () => void;
}

const TRAJECTORY_ORDER: Record<GradeTrend['trajectory'], number> = {
  declining: 0,
  stable: 1,
  improving: 2,
};

const TRAJECTORY_SYMBOL: Record<GradeTrend['trajectory'], string> = {
  improving: '\u25B2',
  declining: '\u25BC',
  stable: '\u25BA',
};

export function CareerPathView({ careerPath, onClose }: CareerPathViewProps) {
  const sortedTrends = [...careerPath.grade_trends].sort(
    (a, b) => TRAJECTORY_ORDER[a.trajectory] - TRAJECTORY_ORDER[b.trajectory],
  );

  return (
    <div className="cpv-container">
      {/* Header */}
      <div className="cpv-header">
        <div className="cpv-header-text">
          <h2>Career Path Analysis</h2>
          <p className="cpv-header-subtitle">
            Based on {careerPath.report_cards_analyzed} report card{careerPath.report_cards_analyzed !== 1 ? 's' : ''}
          </p>
        </div>
        {onClose && (
          <button className="cpv-close-btn" onClick={onClose} type="button">
            Close
          </button>
        )}
      </div>

      {/* Academic Strengths */}
      {careerPath.strengths.length > 0 && (
        <div className="cpv-section">
          <h3 className="cpv-section-title">Academic Strengths</h3>
          <div className="cpv-strengths">
            {careerPath.strengths.map((strength) => (
              <span key={strength} className="cpv-strength-badge">
                {strength}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Grade Trends */}
      {sortedTrends.length > 0 && (
        <div className="cpv-section">
          <h3 className="cpv-section-title">Grade Trends</h3>
          <div className="cpv-trends">
            {sortedTrends.map((trend) => (
              <div key={trend.subject} className="cpv-trend-item">
                <span className={`cpv-trend-indicator ${trend.trajectory}`}>
                  {TRAJECTORY_SYMBOL[trend.trajectory]}
                </span>
                <span className="cpv-trend-subject">{trend.subject}</span>
                <span className="cpv-trend-data">{trend.data}</span>
                {trend.note && (
                  <span className="cpv-trend-note">{trend.note}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Career Suggestions */}
      {careerPath.career_suggestions.length > 0 && (
        <div className="cpv-section">
          <h3 className="cpv-section-title">Career Suggestions</h3>
          <div className="cpv-careers-grid">
            {careerPath.career_suggestions.map((career) => (
              <div key={career.career} className="cpv-career-card">
                <h4 className="cpv-career-title">{career.career}</h4>
                <p className="cpv-career-reasoning">{career.reasoning}</p>
                <div className="cpv-career-subjects">
                  {career.related_subjects.map((subject) => (
                    <span key={subject} className="cpv-subject-tag">
                      {subject}
                    </span>
                  ))}
                </div>
                <div className="cpv-career-next-steps">
                  <span className="cpv-career-next-steps-label">Next steps:</span>
                  {career.next_steps}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Overall Assessment */}
      {careerPath.overall_assessment && (
        <div className="cpv-section">
          <h3 className="cpv-section-title">Overall Assessment</h3>
          <div className="cpv-assessment">
            {careerPath.overall_assessment}
          </div>
        </div>
      )}
    </div>
  );
}
