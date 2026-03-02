import { useState, useEffect, useCallback } from 'react';
import { DashboardLayout } from '../components/DashboardLayout';
import { useAuth } from '../context/AuthContext';
import {
  generatePredictions,
  generateCoursePrediction,
  getPredictions,
  getChildPredictions,
  type GradePredictionResponse,
  type GradePredictionListResponse,
} from '../api/gradePrediction';
import { parentApi, type ChildSummary } from '../api/parent';
import './GradePredictionPage.css';

// ─── Helpers ─────────────────────────────────────────────────────────────────

function gradeColorClass(grade: number): string {
  if (grade >= 70) return 'green';
  if (grade >= 55) return 'yellow';
  return 'red';
}

function trendLabel(trend: string): string {
  switch (trend) {
    case 'improving': return 'Improving';
    case 'declining': return 'Declining';
    default: return 'Stable';
  }
}

function trendArrow(trend: string): string {
  switch (trend) {
    case 'improving': return '↑';
    case 'declining': return '↓';
    default: return '→';
  }
}

// ─── Skeleton Loader ──────────────────────────────────────────────────────────

function PredictionSkeleton() {
  return (
    <div className="gp-skeleton">
      <div className="gp-skeleton-line" style={{ height: 18, width: '60%' }} />
      <div className="gp-skeleton-line" style={{ height: 48, width: '40%' }} />
      <div className="gp-skeleton-line" style={{ height: 8, width: '100%' }} />
      <div className="gp-skeleton-line" style={{ height: 14, width: '90%' }} />
      <div className="gp-skeleton-line" style={{ height: 14, width: '80%' }} />
      <div className="gp-skeleton-line" style={{ height: 14, width: '70%' }} />
    </div>
  );
}

// ─── Prediction Card ─────────────────────────────────────────────────────────

interface PredictionCardProps {
  prediction: GradePredictionResponse;
  onRefresh: (courseId: number | null) => Promise<void>;
  refreshingId: number | null;
}

function PredictionCard({ prediction, onRefresh, refreshingId }: PredictionCardProps) {
  const colorClass = gradeColorClass(prediction.predicted_grade);
  const isRefreshing = refreshingId === (prediction.course_id ?? -1);

  return (
    <div className={`gp-card gp-card--${colorClass}`}>
      <div className="gp-card__header">
        <h3 className="gp-card__course-name">
          {prediction.course_name ?? 'Overall'}
        </h3>
        <span className={`gp-card__trend gp-card__trend--${prediction.trend}`}>
          <span className="gp-trend-arrow">{trendArrow(prediction.trend)}</span>
          {trendLabel(prediction.trend)}
        </span>
      </div>

      <div className="gp-card__grade-row">
        <span className={`gp-card__grade gp-card__grade--${colorClass}`}>
          {prediction.predicted_grade.toFixed(1)}
        </span>
        <span className="gp-card__grade-pct">%</span>
      </div>

      <div className="gp-confidence">
        <span className="gp-confidence__label">Confidence</span>
        <div className="gp-confidence__bar-track">
          <div
            className="gp-confidence__bar-fill"
            style={{ width: `${(prediction.confidence * 100).toFixed(0)}%` }}
          />
        </div>
        <span className="gp-confidence__value">
          {(prediction.confidence * 100).toFixed(0)}%
        </span>
      </div>

      {prediction.factors.length > 0 && (
        <div className="gp-card__factors">
          <p className="gp-card__factors-title">AI Factors</p>
          <ul className="gp-factors-list">
            {prediction.factors.map((f, i) => (
              <li key={i}>{f}</li>
            ))}
          </ul>
        </div>
      )}

      <button
        className="gp-card__refresh-btn"
        onClick={() => onRefresh(prediction.course_id)}
        disabled={isRefreshing}
      >
        {isRefreshing ? 'Refreshing...' : 'Refresh Prediction'}
      </button>
    </div>
  );
}

// ─── Summary Bar ─────────────────────────────────────────────────────────────

interface SummaryBarProps {
  data: GradePredictionListResponse;
}

function SummaryBar({ data }: SummaryBarProps) {
  return (
    <div className="gp-summary-bar">
      <div className="gp-summary-card">
        <span className="gp-summary-card__label">Overall GPA Prediction</span>
        <span className="gp-summary-card__value">
          {data.overall_gpa_prediction !== null
            ? `${data.overall_gpa_prediction.toFixed(1)}%`
            : '—'}
        </span>
        <span className="gp-summary-card__sub">Across all courses</span>
      </div>
      <div className="gp-summary-card">
        <span className="gp-summary-card__label">Strongest Course</span>
        <span className="gp-summary-card__value" style={{ fontSize: '1rem' }}>
          {data.strongest_course ?? '—'}
        </span>
        <span className="gp-summary-card__sub">Highest predicted grade</span>
      </div>
      {data.at_risk_course ? (
        <div className="gp-summary-card gp-summary-card--at-risk">
          <span className="gp-summary-card__label">At-Risk Alert</span>
          <span className="gp-summary-card__value">{data.at_risk_course}</span>
          <span className="gp-summary-card__sub">Predicted below 60%</span>
        </div>
      ) : (
        <div className="gp-summary-card">
          <span className="gp-summary-card__label">Status</span>
          <span className="gp-summary-card__value" style={{ fontSize: '1rem', color: '#16a34a' }}>
            On Track
          </span>
          <span className="gp-summary-card__sub">No courses at risk</span>
        </div>
      )}
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export function GradePredictionPage() {
  const { user } = useAuth();
  const isParent = user?.role === 'parent';

  const [predData, setPredData] = useState<GradePredictionListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [refreshingId, setRefreshingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Parent: child selection
  const [children, setChildren] = useState<ChildSummary[]>([]);
  const [selectedChildId, setSelectedChildId] = useState<number | null>(null);

  // Load children list for parent
  useEffect(() => {
    if (!isParent) return;
    parentApi.getChildren().then((kids) => {
      setChildren(kids);
      if (kids.length > 0) setSelectedChildId(kids[0].user_id);
    }).catch(() => {});
  }, [isParent]);

  // Fetch predictions
  const fetchPredictions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (isParent) {
        if (!selectedChildId) { setLoading(false); return; }
        const data = await getChildPredictions(selectedChildId);
        setPredData(data);
      } else {
        const data = await getPredictions();
        setPredData(data);
      }
    } catch {
      setError('Failed to load predictions. Generate them first or try again.');
      setPredData(null);
    } finally {
      setLoading(false);
    }
  }, [isParent, selectedChildId]);

  useEffect(() => {
    fetchPredictions();
  }, [fetchPredictions]);

  const handleGenerateAll = async () => {
    setGenerating(true);
    setError(null);
    try {
      const data = await generatePredictions();
      setPredData(data);
    } catch {
      setError('Failed to generate predictions. Please try again.');
    } finally {
      setGenerating(false);
    }
  };

  const handleRefreshCourse = async (courseId: number | null) => {
    setRefreshingId(courseId ?? -1);
    setError(null);
    try {
      if (courseId !== null) {
        const updated = await generateCoursePrediction(courseId);
        setPredData((prev) => {
          if (!prev) return prev;
          const newPreds = prev.predictions.map((p) =>
            p.course_id === courseId ? updated : p
          );
          return { ...prev, predictions: newPreds };
        });
      } else {
        // Refresh overall
        const data = await generatePredictions();
        setPredData(data);
      }
    } catch {
      setError('Failed to refresh prediction. Please try again.');
    } finally {
      setRefreshingId(null);
    }
  };

  const hasPredictions = predData && predData.predictions.length > 0;

  return (
    <DashboardLayout welcomeSubtitle="AI-powered grade trajectory analysis">
      <div className="grade-prediction-page">
        {/* Controls row */}
        <div className="gp-controls">
          <h2 className="gp-controls__title">Grade Predictions</h2>

          {isParent && children.length > 0 && (
            <div className="gp-child-selector">
              <label htmlFor="child-select">Viewing:</label>
              <select
                id="child-select"
                value={selectedChildId ?? ''}
                onChange={(e) => setSelectedChildId(Number(e.target.value))}
              >
                {children.map((child) => (
                  <option key={child.user_id} value={child.user_id}>
                    {child.full_name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {!isParent && (
            <button
              className="gp-refresh-btn"
              onClick={handleGenerateAll}
              disabled={generating}
            >
              {generating ? 'Generating...' : 'Refresh All'}
            </button>
          )}
        </div>

        {/* Error */}
        {error && <div className="gp-error">{error}</div>}

        {/* Summary bar */}
        {hasPredictions && !loading && <SummaryBar data={predData} />}

        {/* Loading state */}
        {loading && (
          <div className="gp-cards-grid">
            {[1, 2, 3].map((i) => (
              <PredictionSkeleton key={i} />
            ))}
          </div>
        )}

        {/* Predictions grid */}
        {!loading && hasPredictions && (
          <div className="gp-cards-grid">
            {predData.predictions.map((pred) => (
              <PredictionCard
                key={pred.id}
                prediction={pred}
                onRefresh={isParent ? async () => {} : handleRefreshCourse}
                refreshingId={refreshingId}
              />
            ))}
          </div>
        )}

        {/* Empty state */}
        {!loading && !hasPredictions && !error && !isParent && (
          <div className="gp-empty">
            <div className="gp-empty__icon">&#128200;</div>
            <h3>No Predictions Yet</h3>
            <p>
              Generate AI-powered grade predictions based on your quiz scores,
              assignments, and study activity.
            </p>
            <button
              className="gp-generate-btn"
              onClick={handleGenerateAll}
              disabled={generating}
            >
              {generating ? 'Generating...' : 'Generate Predictions'}
            </button>
          </div>
        )}

        {!loading && !hasPredictions && !error && isParent && (
          <div className="gp-empty">
            <div className="gp-empty__icon">&#128200;</div>
            <h3>No Predictions Available</h3>
            <p>
              {selectedChildId
                ? 'No grade predictions have been generated for this child yet.'
                : 'Select a child to view their grade predictions.'}
            </p>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

export default GradePredictionPage;
