import { useState, useEffect, useCallback } from 'react';
import { DashboardLayout } from '../../components/DashboardLayout';
import { parentApi } from '../../api/parent';
import type { ChildSummary } from '../../api/parent';
import { schoolReportCardsApi } from '../../api/schoolReportCards';
import type {
  SchoolReportCard,
  FullAnalysis,
  CareerPathAnalysis,
  GradeAnalysisItem,
  ImprovementArea,
  ParentTip,
  GradeTrend,
  CareerSuggestion,
} from '../../api/schoolReportCards';
import { ChildSelectorTabs } from '../../components/ChildSelectorTabs';
import { PageSkeleton } from '../../components/Skeleton';
import ReportCardUploadModal from '../../components/parent/ReportCardUploadModal';
import './ReportCardAnalysis.css';

export function ReportCardAnalysis() {
  const [children, setChildren] = useState<ChildSummary[]>([]);
  const [selectedChildId, setSelectedChildId] = useState<number | null>(null);
  const [reportCards, setReportCards] = useState<SchoolReportCard[]>([]);
  const [expandedCardId, setExpandedCardId] = useState<number | null>(null);
  const [selectedAnalysis, setSelectedAnalysis] = useState<FullAnalysis | null>(null);
  const [careerPath, setCareerPath] = useState<CareerPathAnalysis | null>(null);

  // Loading states
  const [loading, setLoading] = useState(true);
  const [listLoading, setListLoading] = useState(false);
  const [analyzeLoadingId, setAnalyzeLoadingId] = useState<number | null>(null);
  const [careerLoading, setCareerLoading] = useState(false);

  // Modal + errors
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showCareerPath, setShowCareerPath] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [careerError, setCareerError] = useState<string | null>(null);

  // Expandable analysis sections
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    subjects: true,
    learningSkills: true,
    improvements: true,
    parentTips: true,
  });

  // Load children on mount
  useEffect(() => {
    (async () => {
      try {
        const kids = await parentApi.getChildren();
        setChildren(kids);
        if (kids.length === 1) {
          setSelectedChildId(kids[0].student_id);
        }
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // Load report cards when child changes
  const loadReportCards = useCallback(async (studentId: number) => {
    setListLoading(true);
    setError(null);
    setReportCards([]);
    setExpandedCardId(null);
    setSelectedAnalysis(null);
    setCareerPath(null);
    setShowCareerPath(false);
    try {
      const resp = await schoolReportCardsApi.list(studentId);
      setReportCards(resp.data);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e.response?.data?.detail || 'Failed to load report cards.');
    } finally {
      setListLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedChildId) {
      loadReportCards(selectedChildId);
    } else {
      setReportCards([]);
      setExpandedCardId(null);
      setSelectedAnalysis(null);
      setCareerPath(null);
      setShowCareerPath(false);
    }
  }, [selectedChildId, loadReportCards]);

  // Select child handler — ChildSelectorTabs can pass null for "all"
  const handleSelectChild = useCallback((studentId: number | null) => {
    if (studentId === null && children.length > 0) {
      setSelectedChildId(children[0].student_id);
    } else {
      setSelectedChildId(studentId);
    }
  }, [children]);

  // Analyze a report card
  const handleAnalyze = useCallback(async (card: SchoolReportCard) => {
    setAnalyzeLoadingId(card.id);
    setError(null);
    try {
      const resp = await schoolReportCardsApi.analyze(card.id);
      setSelectedAnalysis(resp.data);
      setExpandedCardId(card.id);
      // Mark the card as analyzed in local state
      setReportCards(prev =>
        prev.map(c => c.id === card.id ? { ...c, has_analysis: true } : c)
      );
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e.response?.data?.detail || 'Failed to analyze report card.');
    } finally {
      setAnalyzeLoadingId(null);
    }
  }, []);

  // View cached analysis
  const handleViewAnalysis = useCallback(async (card: SchoolReportCard) => {
    if (expandedCardId === card.id) {
      setExpandedCardId(null);
      setSelectedAnalysis(null);
      return;
    }
    setAnalyzeLoadingId(card.id);
    setError(null);
    try {
      const resp = await schoolReportCardsApi.getAnalysis(card.id);
      setSelectedAnalysis(resp.data);
      setExpandedCardId(card.id);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e.response?.data?.detail || 'Failed to load analysis.');
    } finally {
      setAnalyzeLoadingId(null);
    }
  }, [expandedCardId]);

  // Career path analysis
  const handleCareerPath = useCallback(async () => {
    if (!selectedChildId) return;
    if (showCareerPath && careerPath) {
      setShowCareerPath(false);
      return;
    }
    setCareerLoading(true);
    setCareerError(null);
    try {
      const resp = await schoolReportCardsApi.careerPath(selectedChildId);
      setCareerPath(resp.data);
      setShowCareerPath(true);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setCareerError(e.response?.data?.detail || 'Failed to generate career path analysis.');
    } finally {
      setCareerLoading(false);
    }
  }, [selectedChildId, showCareerPath, careerPath]);

  // Toggle analysis section
  const toggleSection = useCallback((section: string) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  }, []);

  const trendArrow = (trajectory: string) => {
    if (trajectory === 'improving') return '\u2197\uFE0F';
    if (trajectory === 'declining') return '\u2198\uFE0F';
    return '\u2794';
  };

  if (loading) {
    return (
      <DashboardLayout>
        <PageSkeleton />
      </DashboardLayout>
    );
  }

  if (children.length === 0) {
    return (
      <DashboardLayout>
        <div className="rca-empty">
          <h2>No children linked</h2>
          <p>Link a child from the My Kids page to view school report cards.</p>
        </div>
      </DashboardLayout>
    );
  }

  const emptyOverdueMap = new Map<number, number>();

  return (
    <DashboardLayout>
      <div className="rca-container">
        <div className="rca-header">
          <h1>School Report Cards</h1>
          <p className="rca-subtitle">Upload, analyze, and track your child's school report cards.</p>
        </div>

        {/* Child selector tabs */}
        <ChildSelectorTabs
          children={children}
          selectedChild={selectedChildId}
          onSelectChild={handleSelectChild}
          childOverdueCounts={emptyOverdueMap}
        />

        {selectedChildId && (
          <>
            {/* Action bar */}
            <div className="rca-action-bar">
              <button
                className="rca-btn"
                onClick={() => setShowUploadModal(true)}
              >
                Upload Report Card
              </button>
              <button
                className="rca-btn rca-btn-secondary"
                onClick={handleCareerPath}
                disabled={reportCards.length === 0 || careerLoading}
              >
                {careerLoading ? 'Generating...' : 'Career Path Analysis'}
              </button>
            </div>

            {error && <div className="rca-error">{error}</div>}
            {careerError && <div className="rca-error">{careerError}</div>}

            {/* Report cards list */}
            {listLoading ? (
              <div className="rca-spinner">Loading report cards...</div>
            ) : reportCards.length === 0 ? (
              <div className="rca-no-cards">
                <p>No report cards uploaded yet. Click "Upload Report Card" to get started.</p>
              </div>
            ) : (
              <div className="rca-list">
                {reportCards.map((card: SchoolReportCard) => (
                  <div
                    key={card.id}
                    className={`rca-card ${expandedCardId === card.id ? 'rca-card-expanded' : ''}`}
                  >
                    <button
                      className="rca-card-header"
                      onClick={() => card.has_analysis ? handleViewAnalysis(card) : undefined}
                      style={{ cursor: card.has_analysis ? 'pointer' : 'default' }}
                    >
                      <div className="rca-card-info">
                        <h3>{card.original_filename}</h3>
                        <p className="rca-card-meta">
                          {card.term && <span>{card.term}</span>}
                          {card.grade_level && <span>Grade {card.grade_level}</span>}
                          {card.school_name && <span>{card.school_name}</span>}
                          <span>{new Date(card.created_at).toLocaleDateString()}</span>
                        </p>
                      </div>
                      <div className="rca-card-actions">
                        <span className={`rca-badge ${card.has_analysis ? 'rca-badge-analyzed' : 'rca-badge-pending'}`}>
                          {card.has_analysis ? 'Analyzed' : 'Not Analyzed'}
                        </span>
                        {card.has_analysis ? (
                          <button
                            className="rca-action-btn rca-action-btn-outline"
                            onClick={(e: React.MouseEvent) => { e.stopPropagation(); handleViewAnalysis(card); }}
                            disabled={analyzeLoadingId === card.id}
                          >
                            {analyzeLoadingId === card.id ? 'Loading...' : expandedCardId === card.id ? 'Hide' : 'View Analysis'}
                          </button>
                        ) : (
                          <button
                            className="rca-action-btn"
                            onClick={(e: React.MouseEvent) => { e.stopPropagation(); handleAnalyze(card); }}
                            disabled={analyzeLoadingId === card.id}
                          >
                            {analyzeLoadingId === card.id ? 'Analyzing...' : 'Analyze Now'}
                          </button>
                        )}
                      </div>
                    </button>

                    {/* Expanded analysis view */}
                    {expandedCardId === card.id && selectedAnalysis && (
                      <div className="rca-card-body">
                        {/* Overall Summary */}
                        <div className="rca-analysis-summary">{selectedAnalysis.overall_summary}</div>

                        {/* Teacher Feedback Summary */}
                        {selectedAnalysis.teacher_feedback_summary && (
                          <div className="rca-analysis-section">
                            <h4>Teacher Feedback Summary</h4>
                            <p>{selectedAnalysis.teacher_feedback_summary}</p>
                          </div>
                        )}

                        {/* Subjects (grade_analysis) */}
                        <div className="rca-analysis-section">
                          <h4 onClick={() => toggleSection('subjects')}>
                            <span className="rca-toggle">{expandedSections.subjects ? '\u25B2' : '\u25BC'}</span>
                            Subjects ({selectedAnalysis.grade_analysis.length})
                          </h4>
                          {expandedSections.subjects && selectedAnalysis.grade_analysis.map((subj: GradeAnalysisItem, i: number) => (
                            <div key={i} className="rca-subject-card">
                              <div className="rca-subject-header">
                                <strong>{subj.subject}</strong>
                                {subj.grade && <span className="rca-subject-grade">{subj.grade}</span>}
                                {subj.level !== null && <span className="rca-subject-grade">Level {subj.level}</span>}
                              </div>
                              {subj.teacher_comment && <p>{subj.teacher_comment}</p>}
                              {subj.feedback && <p className="rca-subject-feedback">{subj.feedback}</p>}
                            </div>
                          ))}
                        </div>

                        {/* Learning Skills */}
                        {selectedAnalysis.learning_skills && (
                          <div className="rca-analysis-section">
                            <h4 onClick={() => toggleSection('learningSkills')}>
                              <span className="rca-toggle">{expandedSections.learningSkills ? '\u25B2' : '\u25BC'}</span>
                              Learning Skills ({selectedAnalysis.learning_skills.ratings.length})
                            </h4>
                            {expandedSections.learningSkills && (
                              <>
                                <div className="rca-tag-list">
                                  {selectedAnalysis.learning_skills.ratings.map((r, i: number) => (
                                    <span key={i} className="rca-tag">{r.skill}: {r.rating}</span>
                                  ))}
                                </div>
                                {selectedAnalysis.learning_skills.summary && (
                                  <p>{selectedAnalysis.learning_skills.summary}</p>
                                )}
                              </>
                            )}
                          </div>
                        )}

                        {/* Improvement Areas */}
                        {selectedAnalysis.improvement_areas.length > 0 && (
                          <div className="rca-analysis-section">
                            <h4 onClick={() => toggleSection('improvements')}>
                              <span className="rca-toggle">{expandedSections.improvements ? '\u25B2' : '\u25BC'}</span>
                              Areas for Improvement ({selectedAnalysis.improvement_areas.length})
                            </h4>
                            {expandedSections.improvements && (
                              <ul className="rca-rec-list">
                                {selectedAnalysis.improvement_areas.map((a: ImprovementArea, i: number) => (
                                  <li key={i}>
                                    <span className="rca-rec-icon">{'\u26A0\uFE0F'}</span>
                                    <div>
                                      <strong>{a.area}</strong> ({a.priority})
                                      <br />
                                      {a.detail}
                                    </div>
                                  </li>
                                ))}
                              </ul>
                            )}
                          </div>
                        )}

                        {/* Parent Tips */}
                        {selectedAnalysis.parent_tips.length > 0 && (
                          <div className="rca-analysis-section">
                            <h4 onClick={() => toggleSection('parentTips')}>
                              <span className="rca-toggle">{expandedSections.parentTips ? '\u25B2' : '\u25BC'}</span>
                              Recommendations ({selectedAnalysis.parent_tips.length})
                            </h4>
                            {expandedSections.parentTips && (
                              <ul className="rca-rec-list">
                                {selectedAnalysis.parent_tips.map((r: ParentTip, i: number) => (
                                  <li key={i}>
                                    <span className="rca-rec-icon">{'\u{1F4A1}'}</span>
                                    <div>
                                      {r.tip}
                                      {r.related_subject && (
                                        <span className="rca-tag" style={{ marginLeft: '0.5rem' }}>{r.related_subject}</span>
                                      )}
                                    </div>
                                  </li>
                                ))}
                              </ul>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Career Path Analysis */}
            {showCareerPath && careerPath && (
              <div className="rca-career-section">
                <h2>Career Path Analysis</h2>
                <p className="rca-career-summary">{careerPath.overall_assessment}</p>

                {/* Strengths */}
                {careerPath.strengths.length > 0 && (
                  <div className="rca-analysis-section">
                    <h4>Key Strengths</h4>
                    <ul className="rca-rec-list">
                      {careerPath.strengths.map((s: string, i: number) => (
                        <li key={i}>
                          <span className="rca-rec-icon">{'\u2B50'}</span>
                          {s}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Trends */}
                {careerPath.grade_trends.length > 0 && (
                  <div className="rca-analysis-section">
                    <h4>Subject Trends</h4>
                    {careerPath.grade_trends.map((t: GradeTrend, i: number) => (
                      <div key={i} className="rca-trend-item">
                        <span className="rca-trend-arrow">{trendArrow(t.trajectory)}</span>
                        <div>
                          <strong>{t.subject}</strong> — {t.note}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Career Suggestions */}
                {careerPath.career_suggestions.length > 0 && (
                  <div className="rca-analysis-section">
                    <h4>Suggested Career Paths</h4>
                    <div className="rca-career-grid">
                      {careerPath.career_suggestions.map((c: CareerSuggestion, i: number) => (
                        <div key={i} className="rca-career-card">
                          <h4>{c.career}</h4>
                          <p>{c.reasoning}</p>
                          {c.next_steps && <p><strong>Next steps:</strong> {c.next_steps}</p>}
                          <div className="rca-tag-list">
                            {c.related_subjects.map((s: string, j: number) => (
                              <span key={j} className="rca-tag">{s}</span>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {/* Upload Modal */}
        {showUploadModal && selectedChildId && (
          <ReportCardUploadModal
            isOpen={showUploadModal}
            onClose={() => setShowUploadModal(false)}
            studentId={selectedChildId}
            studentName={children.find(c => c.student_id === selectedChildId)?.full_name || ''}
            onUploadComplete={() => { setShowUploadModal(false); loadReportCards(selectedChildId); }}
          />
        )}
      </div>
    </DashboardLayout>
  );
}
