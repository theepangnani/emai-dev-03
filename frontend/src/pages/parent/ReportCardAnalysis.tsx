import { useState, useEffect, useCallback } from 'react';
import { DashboardLayout } from '../../components/DashboardLayout';
import { useConfirm } from '../../components/ConfirmModal';
import { parentApi } from '../../api/parent';
import type { ChildSummary } from '../../api/parent';
import { schoolReportCardsApi } from '../../api/schoolReportCards';
import type {
  SchoolReportCard,
  FullAnalysis,
  CareerPathAnalysis,
} from '../../api/schoolReportCards';
import { ChildSelectorTabs } from '../../components/ChildSelectorTabs';
import { PageSkeleton } from '../../components/Skeleton';
import ReportCardUploadModal from '../../components/parent/ReportCardUploadModal';
import { ReportCardAnalysisView } from '../../components/parent/ReportCardAnalysisView';
import { CareerPathView } from '../../components/parent/CareerPathView';
import './ReportCardAnalysis.css';

export function ReportCardAnalysis() {
  const { confirm, confirmModal } = useConfirm();
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

  // Delete handler
  const handleDelete = useCallback(async (cardId: number) => {
    const confirmed = await confirm({
      title: 'Delete Report Card',
      message: 'Delete this report card? This cannot be undone.',
      confirmLabel: 'Delete',
      variant: 'danger',
    });
    if (!confirmed) return;
    try {
      await schoolReportCardsApi.delete(cardId);
      if (selectedChildId) loadReportCards(selectedChildId);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e.response?.data?.detail || 'Failed to delete report card.');
    }
  }, [confirm, selectedChildId, loadReportCards]);

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
                        <button
                          className="rca-action-btn rca-action-btn-outline"
                          style={{ color: 'var(--danger, #e74c3c)', borderColor: 'var(--danger, #e74c3c)' }}
                          onClick={(e: React.MouseEvent) => { e.stopPropagation(); handleDelete(card.id); }}
                        >
                          Delete
                        </button>
                      </div>
                    </button>

                    {/* Expanded analysis view */}
                    {expandedCardId === card.id && selectedAnalysis && (
                      <ReportCardAnalysisView
                        analysis={selectedAnalysis}
                        reportCard={card}
                        onClose={() => { setExpandedCardId(null); setSelectedAnalysis(null); }}
                      />
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Career Path Analysis */}
            {showCareerPath && careerPath && (
              <CareerPathView careerPath={careerPath} onClose={() => setShowCareerPath(false)} />
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
      {confirmModal}
    </DashboardLayout>
  );
}
