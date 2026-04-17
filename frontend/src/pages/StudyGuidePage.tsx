import { Suspense, useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useParams, useNavigate, useLocation, useSearchParams, Link } from 'react-router-dom';
import { studyApi } from '../api/client';
import type { StudyGuide, ResolvedStudent } from '../api/client';
import StudyGuideSuggestionChips, { ASK_BOT_LABEL, FULL_GUIDE_LABEL } from '../components/StudyGuideSuggestionChips';
import type { SuggestionTopic } from '../components/StudyGuideSuggestionChips';
import { useAuth } from '../context/AuthContext';
import { ileApi } from '../api/ile';
import { DashboardLayout } from '../components/DashboardLayout';
import { CreateTaskModal } from '../components/CreateTaskModal';
import { MaterialContextMenu } from '../components/MaterialContextMenu';
import { EditStudyGuideModal } from '../components/EditStudyGuideModal';
import { ContentCard, MarkdownBody, MarkdownErrorBoundary } from '../components/ContentCard';
import { TableOfContents } from '../components/TableOfContents';
import { CollapsibleMarkdown } from '../components/CollapsibleMarkdown';
import { useConfirm } from '../components/ConfirmModal';
import { FAQErrorHint } from '../components/FAQErrorHint';
import { extractFaqCode } from '../utils/faqUtils';
import { downloadAsPdf } from '../utils/exportUtils';
import { PageNav } from '../components/PageNav';
import { useAIUsage } from '../hooks/useAIUsage';
import { AILimitRequestModal } from '../components/AILimitRequestModal';
import { useRegisterNotesFAB, useFABContext } from '../context/FABContext';
import { NotesPanel } from '../components/NotesPanel';
import { SelectionTooltip } from '../components/SelectionTooltip';
import { TextSelectionContextMenu } from '../components/TextSelectionContextMenu';
import { SubGuidesPanel } from '../components/SubGuidesPanel';
import { StudyGuideBreadcrumb } from '../components/StudyGuideBreadcrumb';
import { useTextSelection } from '../hooks/useTextSelection';
import { useHighlightRenderer } from '../hooks/useHighlightRenderer';
import { useStudyGuideStream } from '../hooks/useStudyGuideStream';
import { StreamingMarkdown } from '../components/StreamingMarkdown';
import '../components/HighlightOverlay.css';
import { JourneyNudgeBanner } from '../components/JourneyNudgeBanner';
import { ResourceLinksSection } from '../components/ResourceLinksSection';
import './StudyGuidePage.css';

const GUIDE_TYPE_LABELS: Record<string, string> = {
  study_guide: 'Study Guide',
  quiz: 'Quiz',
  flashcards: 'Flashcards',
};

export function StudyGuidePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const isGeneratingRoute = id === 'generating';
  const [guide, setGuide] = useState<StudyGuide | null>(null);
  const [loading, setLoading] = useState(!isGeneratingRoute);
  const [error, setError] = useState<string | null>(null);
  const [faqCode, setFaqCode] = useState<string | null>(null);
  const [showTaskModal, setShowTaskModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showTaskPrompt, setShowTaskPrompt] = useState(false);
  const [exporting, setExporting] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);
  const { confirm, confirmModal, getLastPromptValue } = useConfirm();
  const { user } = useAuth();
  const isParent = user?.role === 'parent' || (user?.roles ?? []).includes('parent');
  const [resolvedStudent, setResolvedStudent] = useState<ResolvedStudent | null>(null);
  const { atLimit, remaining, invalidate: refreshAIUsage } = useAIUsage();
  const [showLimitModal, setShowLimitModal] = useState(false);
  const [notesOpen, setNotesOpen] = useState(false);
  const toggleNotes = useCallback(() => setNotesOpen(v => !v), []);
  useRegisterNotesFAB(guide?.course_content_id ? { courseContentId: guide.course_content_id, isOpen: notesOpen, onToggle: toggleNotes } : null);
  // §6.114 — Register study guide context for chatbot Q&A mode
  const { setStudyGuideContext, openChatWithQuestion } = useFABContext();
  useEffect(() => {
    if (guide) {
      setStudyGuideContext({ id: guide.id, title: guide.title, courseId: guide.course_id ?? undefined });
    }
    return () => setStudyGuideContext(null);
  }, [guide?.id, guide?.title, guide?.course_id, setStudyGuideContext]);
  const [appendText, setAppendText] = useState<string | null>(null);
  const [parentGuideTitle, setParentGuideTitle] = useState<string | null>(null);
  const [showScrollTop, setShowScrollTop] = useState(false);
  const [highlights, setHighlights] = useState<{text: string}[]>([]);
  const [addHighlight, setAddHighlight] = useState<{text: string} | null>(null);
  const [removeHighlightText, setRemoveHighlightText] = useState<string | null>(null);
  const [childGuides, setChildGuides] = useState<StudyGuide[]>([]);
  const [generatingTopic, setGeneratingTopic] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [flashTutorLoading, setFlashTutorLoading] = useState(false);
  const stream = useStudyGuideStream();
  const { selection, clearSelection } = useTextSelection(contentRef);
  const handleHighlightClick = useCallback((text: string) => {
    // Immediately update visual highlights for instant feedback
    setHighlights(prev => prev.filter(h => h.text !== text));
    // Tell NotesPanel to persist the removal
    setRemoveHighlightText(text);
  }, []);
  useHighlightRenderer(contentRef, highlights, handleHighlightClick);

  useEffect(() => {
    const onScroll = () => {
      const y = window.scrollY ?? document.documentElement.scrollTop ?? 0;
      setShowScrollTop(y > 200);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const handleScrollTop = () => { window.scrollTo({ top: 0, behavior: 'smooth' }); };

  const handleAddToNotes = (text?: string) => {
    const noteText = text || selection?.text;
    if (!noteText) return;
    setAppendText(noteText);
    setAddHighlight({ text: noteText });
    setNotesOpen(true);
    clearSelection();
    window.getSelection()?.removeAllRanges();
  };

  // Detect first-time guide view from navigation state
  const isNewGuide = !!(location.state as any)?.newGuide;

  useEffect(() => {
    const fetchGuide = async () => {
      if (!id || isGeneratingRoute) return;
      try {
        const data = await studyApi.getGuide(parseInt(id));
        setGuide(data);
        // Auto-mark shared guide as viewed (#1414)
        if (data.shared_with_user_id && data.shared_with_user_id === user?.id) {
          studyApi.markViewed(data.id).catch(() => {});
        }
        // Show task prompt for new/regenerated guides
        if (isNewGuide) {
          setShowTaskPrompt(true);
        }
      } catch (err: unknown) {
        const status = (err as { response?: { status?: number } })?.response?.status;
        if (status === 404) {
          setError('This study guide no longer exists. It may have been deleted or archived.');
        } else {
          setError('Failed to load study guide. Please try again.');
        }
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchGuide();
  }, [id]);

  // Redirect to course-materials tab when guide has a parent material (#1837, #1969)
  // Skip redirect if opened from class materials tab (fromMaterial state)
  const fromMaterial = (location.state as { fromMaterial?: boolean })?.fromMaterial;
  useEffect(() => {
    if (guide && guide.course_content_id && !fromMaterial) {
      navigate(`/course-materials/${guide.course_content_id}?tab=guide`, { replace: true });
    }
  }, [guide, navigate, fromMaterial]);

  // Fetch parent guide title for sub-guides (#1594)
  useEffect(() => {
    if (!guide?.parent_guide_id) { setParentGuideTitle(null); return; }
    // Only show for sub_guides, not version regenerations
    if (guide.relationship_type && guide.relationship_type !== 'sub_guide') { setParentGuideTitle(null); return; }
    studyApi.getGuide(guide.parent_guide_id)
      .then(parent => setParentGuideTitle(parent.title))
      .catch(() => setParentGuideTitle(null));
  }, [guide?.parent_guide_id, guide?.relationship_type]);

  // Fetch child guides (sub-guides) for this guide (#1594)
  // If this guide is itself a sub-guide, fetch siblings from the parent (#2095)
  useEffect(() => {
    if (!guide) return;
    const fetchId = guide.parent_guide_id && (!guide.relationship_type || guide.relationship_type === 'sub_guide')
      ? guide.parent_guide_id
      : guide.id;
    studyApi.listChildGuides(fetchId)
      .then(setChildGuides)
      .catch(() => setChildGuides([]));
  }, [guide?.id, guide?.parent_guide_id, guide?.relationship_type]);

  // Resolve child student for parent role
  useEffect(() => {
    if (!isParent || !guide) return;
    const params = guide.course_id
      ? { course_id: guide.course_id }
      : { study_guide_id: guide.id };
    studyApi.resolveStudent(params)
      .then(setResolvedStudent)
      .catch(() => {});
  }, [isParent, guide?.course_id, guide?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleDelete = async () => {
    if (!guide) return;
    const ok = await confirm({ title: 'Delete Study Guide', message: 'Are you sure you want to delete this study guide? This cannot be undone.', confirmLabel: 'Delete', variant: 'danger' });
    if (!ok) return;
    try {
      await studyApi.deleteGuide(guide.id);
      navigate('/dashboard');
    } catch {
      setError('Failed to delete study guide');
    }
  };

  const handleRegenerate = async () => {
    if (!guide) return;
    if (atLimit) {
      setShowLimitModal(true);
      return;
    }
    const ok = await confirm({
      title: 'Regenerate Study Guide',
      message: `This will use 1 AI credit. You have ${remaining} remaining. Continue?`,
      confirmLabel: 'Regenerate',
      promptLabel: 'Focus on (optional)',
      promptPlaceholder: 'e.g., photosynthesis, the Calvin cycle',
      ...(remaining <= 0 ? {
        disableConfirm: true,
        extraActionLabel: 'Request More Credits',
        onExtraAction: () => setShowLimitModal(true),
      } : {}),
    });
    if (!ok) return;
    const focusPrompt = getLastPromptValue();
    try {
      const result = await studyApi.generateGuide({
        title: guide.title.replace(/^Study Guide: /, ''),
        content: guide.content,
        regenerate_from_id: guide.id,
        ...(focusPrompt ? { focus_prompt: focusPrompt } : {}),
      });
      refreshAIUsage();
      navigate(result.course_content_id ? `/course-materials/${result.course_content_id}?tab=guide` : `/study/guide/${result.id}`);
    } catch (err) {
      setError('Failed to regenerate');
      setFaqCode(extractFaqCode(err));
    }
  };

  const handleFlashTutor = async () => {
    if (!guide || flashTutorLoading) return;
    setFlashTutorLoading(true);
    setError(null);
    try {
      const session = await ileApi.createSessionFromStudyGuide({
        study_guide_id: guide.id,
        course_content_id: guide.course_content_id ?? undefined,
      });
      navigate(`/flash-tutor/session/${session.id}`);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || 'Failed to start Flash Tutor session');
    } finally {
      setFlashTutorLoading(false);
    }
  };

  const parsedSuggestionTopics: SuggestionTopic[] = useMemo(() => {
    if (!guide?.suggestion_topics) return [];
    try {
      const topics = JSON.parse(guide.suggestion_topics) as SuggestionTopic[];
      return [
        ...topics,
        { label: FULL_GUIDE_LABEL, description: 'Generate a complete detailed study guide with explanations and examples' },
        { label: ASK_BOT_LABEL, description: 'Ask the AI chatbot any question about this material' },
      ];
    } catch {
      return [];
    }
  }, [guide?.suggestion_topics]);

  // Auto-start streaming when navigated to /study/guide/generating (#2882)
  const generationStartedRef = useRef(false);
  useEffect(() => {
    if (!isGeneratingRoute || generationStartedRef.current) return;
    const parentGuideId = searchParams.get('parentGuideId');
    const topic = searchParams.get('topic');
    const guideType = searchParams.get('guideType') || 'study_guide';
    if (!parentGuideId || !topic) return;
    generationStartedRef.current = true;
    setGeneratingTopic(topic);
    const extra: Record<string, string | number> = {};
    const customPrompt = searchParams.get('customPrompt');
    const maxTokens = searchParams.get('maxTokens');
    const documentType = searchParams.get('documentType');
    const studyGoal = searchParams.get('studyGoal');
    if (customPrompt) extra.custom_prompt = customPrompt;
    if (maxTokens) extra.max_tokens = parseInt(maxTokens, 10);
    if (documentType) extra.document_type = documentType;
    if (studyGoal) extra.study_goal = studyGoal;
    stream.startStream(
      { topic, guide_type: guideType, ...extra } as any,
      { endpoint: `/api/study/guides/${parentGuideId}/generate-child-stream` },
    );
  }, [isGeneratingRoute]); // eslint-disable-line react-hooks/exhaustive-deps

  // Handle streaming child guide completion
  useEffect(() => {
    if (stream.status === 'done') {
      setGeneratingTopic(null);
      refreshAIUsage();
      if (stream.guide) {
        // Navigate to the completed child guide
        navigate(`/study/guide/${stream.guide.id}`, { state: { fromMaterial: true } });
        stream.reset();
      }
    }
    if (stream.status === 'error') {
      setGeneratingTopic(null);
      if (stream.error) {
        setToast(stream.error);
        setTimeout(() => setToast(null), 4000);
      }
      if (isGeneratingRoute) {
        // Go back on error during generation
        navigate(-1);
      }
      stream.reset();
    }
  }, [stream.status]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleChipClick = async (topic: SuggestionTopic) => {
    if (!guide) return;
    if (topic.label === ASK_BOT_LABEL) {
      window.dispatchEvent(new Event('open-help-chat'));
      return;
    }
    if (atLimit) {
      setShowLimitModal(true);
      return;
    }
    setGeneratingTopic(topic.label);
    const extra = topic.label === FULL_GUIDE_LABEL ? {
      custom_prompt: 'Generate a comprehensive, detailed study guide covering ALL topics from the source material. Include: detailed explanations of each concept, worked examples with step-by-step solutions, practice problems, common mistakes to avoid, and key formulas/rules. This should be thorough enough for a student to study from independently.',
      max_tokens: 4000,
    } : {};
    stream.startStream(
      { topic: topic.label, guide_type: 'study_guide', ...extra } as any,
      { endpoint: `/api/study/guides/${guide.id}/generate-child-stream` },
    );
  };

  if (loading) {
    return (
      <DashboardLayout showBackButton headerSlot={() => null}>
        <div className="study-guide-page">
          <div className="loading">Loading study guide...</div>
        </div>
      </DashboardLayout>
    );
  }

  // Generating route: show streaming content while sub-guide is being created (#2882)
  if (isGeneratingRoute) {
    const genTopic = searchParams.get('topic') || 'Sub-guide';
    return (
      <DashboardLayout showBackButton headerSlot={() => null}>
        <div className="study-guide-page">
          <PageNav items={[
            { label: 'Home', to: '/dashboard' },
            { label: 'Class Materials', to: '/course-materials' },
            { label: 'Generating...' },
          ]} />
          <div className="sg-detail-header">
            <div className="sg-title-row">
              <span className="sg-title-icon" aria-hidden="true">&#128214;</span>
              <h2>{genTopic}</h2>
            </div>
          </div>
          <div ref={contentRef}>
            <ContentCard>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem', color: 'var(--color-text-secondary, #666)' }}>
                <span style={{ display: 'inline-block', width: '14px', height: '14px', border: '2px solid currentColor', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
                <span>Generating sub-guide...</span>
              </div>
              {stream.content ? (
                <StreamingMarkdown content={stream.content} isStreaming={stream.isStreaming} />
              ) : (
                <div style={{ color: 'var(--color-text-tertiary, #999)', fontStyle: 'italic' }}>Starting generation...</div>
              )}
            </ContentCard>
          </div>
          {confirmModal}
        </div>
      </DashboardLayout>
    );
  }

  if (error || !guide) {
    return (
      <DashboardLayout showBackButton headerSlot={() => null}>
        <div className="study-guide-page">
          <div className="error">{error || 'Study guide not found'}</div>
          <FAQErrorHint faqCode={faqCode} />
          <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', marginTop: '1rem' }}>
            <Link to="/course-materials" className="back-link">View All Study Materials</Link>
            <Link to="/dashboard" className="back-link">Back to Dashboard</Link>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  const guideTypeLabel = GUIDE_TYPE_LABELS[guide.guide_type] || guide.guide_type;

  return (
    <DashboardLayout showBackButton headerSlot={() => null}>
    <div className="study-guide-page">
      <PageNav items={[
        { label: 'Home', to: '/dashboard' },
        { label: 'Class Materials', to: '/course-materials' },
        ...(guide?.course_content_id
          ? [{ label: guide.title.replace(/^Study Guide:\s*/i, ''), to: `/course-materials/${guide.course_content_id}?tab=guide` }]
          : []),
        { label: guide.parent_guide_id && (!guide.relationship_type || guide.relationship_type === 'sub_guide')
          ? guide.title.replace(/^Study Guide:\s*/i, '')
          : 'Study Guide' },
      ]} />

      {guide.parent_guide_id && (!guide.relationship_type || guide.relationship_type === 'sub_guide') && (
        <StudyGuideBreadcrumb guideId={guide.id} />
      )}
      <JourneyNudgeBanner pageName="study-guide-detail" />

      {/* Header card */}
      <div className="sg-detail-header">
        <div className="sg-title-row">
          <span className="sg-title-icon" aria-hidden="true">&#128214;</span>
          <h2>
            {guide.title}
            {guide.parent_guide_id && (!guide.relationship_type || guide.relationship_type === 'sub_guide') && (
              <span className="sg-sub-badge">Sub-Guide</span>
            )}
          </h2>
          <MaterialContextMenu items={[
            { label: 'Create Study Guide', icon: <svg width="16" height="16" viewBox="0 0 20 20" fill="none"><path d="M4 2h8l4 4v10a2 2 0 01-2 2H4a2 2 0 01-2-2V4a2 2 0 012-2z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/><path d="M8 10l2 2 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>, onClick: () => handleRegenerate() },
            { label: 'Create Task', icon: <svg width="16" height="16" viewBox="0 0 20 20" fill="none"><rect x="3" y="2" width="14" height="16" rx="2" stroke="currentColor" strokeWidth="1.6"/><path d="M7 7h6M7 10.5h3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/><circle cx="14.5" cy="14.5" r="4.5" fill="var(--color-accent-strong, #2a9fa8)"/><path d="M14.5 12.5v4M12.5 14.5h4" stroke="#fff" strokeWidth="1.4" strokeLinecap="round"/></svg>, onClick: () => setShowTaskModal(true) },
            { label: 'Edit Class Material', icon: <svg width="16" height="16" viewBox="0 0 20 20" fill="none"><path d="M13.586 3.586a2 2 0 112.828 2.828l-9.5 9.5L3 17l1.086-3.914 9.5-9.5z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>, onClick: () => setShowEditModal(true) },
          ]} />
        </div>
        <div className="sg-meta-row">
          <span className="sg-type-badge">{guideTypeLabel}</span>
          {guide.parent_guide_id && (!guide.relationship_type || guide.relationship_type === 'sub_guide') && guide.generation_context && (
            <span className="sg-topic-badge" title={guide.generation_context}>
              {guide.generation_context.length > 60 ? guide.generation_context.slice(0, 57) + '...' : guide.generation_context}
            </span>
          )}
          {guide.version > 1 && <span className="sg-version-badge">v{guide.version}</span>}
          <span className="sg-date">{new Date(guide.created_at).toLocaleDateString()}</span>
          {childGuides.length > 0 && (
            <button className="sg-sub-guides-badge" onClick={() => {
              document.querySelector('.sg-sub-guides-section')?.scrollIntoView({ behavior: 'smooth' });
            }}>
              Sub-Guides ({childGuides.length})
            </button>
          )}
          <div className="sg-icon-actions">
            <button
              className="sg-flash-tutor-btn"
              title="Practice with Flash Tutor"
              aria-label="Practice with Flash Tutor"
              onClick={handleFlashTutor}
              disabled={flashTutorLoading}
            >
              {flashTutorLoading ? 'Starting...' : 'Practice'}
            </button>
            {/* Notes FAB at bottom-right replaces inline toggle */}
            <button className="sg-icon-btn" title="Regenerate" aria-label="Regenerate study guide" onClick={handleRegenerate}>&#8635;</button>
            <button className="sg-icon-btn" title="Print" aria-label="Print study guide" onClick={() => window.print()}>&#128424;</button>
            <button className="sg-icon-btn" title="Download PDF" aria-label="Download PDF" disabled={exporting} onClick={async () => { if (!contentRef.current) return; setExporting(true); try { await downloadAsPdf(contentRef.current, guide.title || 'study-guide'); } finally { setExporting(false); } }}>{exporting ? '\u23F3' : '\u{1F4E5}'}</button>
            <button className="sg-icon-btn sg-icon-btn-danger" title="Delete" aria-label="Delete study guide" onClick={handleDelete}>&#128465;</button>
          </div>
        </div>
      </div>

      {parentGuideTitle && guide?.parent_guide_id && (
        <div className="sg-parent-link-banner">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path d="M6 12l-4-4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M2 8h12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          <span>Generated from: </span>
          <Link to={guide.course_content_id ? `/course-materials/${guide.course_content_id}?tab=guide` : `/study/guide/${guide.parent_guide_id}`} className="sg-parent-link">
            {parentGuideTitle}
          </Link>
        </div>
      )}

      {showTaskPrompt && (
        <div className="task-prompt-banner">
          <span>Want to create a study task for this guide?</span>
          <button onClick={() => { setShowTaskModal(true); setShowTaskPrompt(false); }}>
            Create Task
          </button>
          <button className="skip-btn" onClick={() => setShowTaskPrompt(false)}>
            Skip
          </button>
        </div>
      )}

      {guide.parent_guide_id && <TableOfContents content={guide.content} />}
      <div ref={contentRef}>
        <ContentCard>
          {guide.parent_guide_id ? (
            <CollapsibleMarkdown content={guide.content} guideId={guide.id} courseContentId={guide.course_content_id ?? undefined} />
          ) : (
            <MarkdownErrorBoundary>
              <Suspense fallback={<div className="content-card-render-loading">Formatting study guide...</div>}>
                <MarkdownBody content={guide.content} courseContentId={guide.course_content_id ?? undefined} />
              </Suspense>
            </MarkdownErrorBoundary>
          )}
        </ContentCard>
      </div>

      {guide.course_content_id && (
        <ResourceLinksSection courseContentId={guide.course_content_id} />
      )}

      {/* Streaming sub-guide content shown inline while generating */}
      {stream.isStreaming && generatingTopic && !isGeneratingRoute && (
        <div className="sg-streaming-child" style={{ marginTop: '1.5rem' }}>
          <ContentCard>
            <div className="sg-streaming-header" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem', color: 'var(--color-text-secondary, #666)' }}>
              <span className="sg-streaming-spinner" style={{ display: 'inline-block', width: '14px', height: '14px', border: '2px solid currentColor', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
              <span>Generating: {generatingTopic}</span>
            </div>
            {stream.content ? (
              <StreamingMarkdown content={stream.content} isStreaming={true} />
            ) : (
              <div style={{ color: 'var(--color-text-tertiary, #999)', fontStyle: 'italic' }}>Starting generation...</div>
            )}
          </ContentCard>
        </div>
      )}

      <SubGuidesPanel childGuides={childGuides} parentGuideId={guide.parent_guide_id || guide.id} currentGuideId={guide.parent_guide_id ? guide.id : undefined} />

      {parsedSuggestionTopics.length > 0 && (
        <StudyGuideSuggestionChips
          topics={parsedSuggestionTopics}
          onTopicClick={handleChipClick}
          disabled={atLimit || stream.isStreaming}
          generatingTopic={generatingTopic}
        />
      )}

      <CreateTaskModal
        open={showTaskModal}
        onClose={() => setShowTaskModal(false)}
        prefillTitle={`Review: ${guide.title}`}
        studyGuideId={guide.id}
        courseId={guide.course_id ?? undefined}
        linkedEntityLabel={`Study Guide: ${guide.title}`}
      />
      {showEditModal && (
        <EditStudyGuideModal
          guide={guide}
          onClose={() => setShowEditModal(false)}
          onSaved={(updated) => { setGuide(updated); setShowEditModal(false); }}
        />
      )}
      {confirmModal}
      <AILimitRequestModal open={showLimitModal} onClose={() => setShowLimitModal(false)} />
      {toast && <div className="toast-notification">{toast}</div>}

      {/* Contextual notes: selection tooltip + FAB + panel */}
      {selection && (
        <SelectionTooltip
          rect={selection.rect}
          visible
          onAddToNotes={handleAddToNotes}
          onAskChatBot={() => {
            if (selection) {
              openChatWithQuestion(selection.text);
              clearSelection();
              window.getSelection()?.removeAllRanges();
            }
          }}
          onStartSession={() => {
            if (selection) {
              navigate('/ask?question=' + encodeURIComponent(selection.text));
              clearSelection();
              window.getSelection()?.removeAllRanges();
            }
          }}
        />
      )}
      <TextSelectionContextMenu
        containerRef={contentRef}
        onAddNote={handleAddToNotes}
        onAskChatBot={(text) => openChatWithQuestion(text)}
      />
      {guide.course_content_id && (
        <>
          <NotesPanel
            courseContentId={guide.course_content_id}
            isOpen={notesOpen}
            onClose={() => setNotesOpen(false)}
            appendText={appendText}
            onAppendConsumed={() => setAppendText(null)}
            addHighlight={addHighlight}
            onHighlightConsumed={() => setAddHighlight(null)}
            onHighlightsChange={setHighlights}
            readOnly={isParent && !!resolvedStudent}
            childStudentId={isParent ? resolvedStudent?.student_user_id : undefined}
            childName={isParent ? resolvedStudent?.student_name : undefined}
            removeHighlightText={removeHighlightText}
            onRemoveHighlightConsumed={() => setRemoveHighlightText(null)}
          />
        </>
      )}
      {showScrollTop && (
        <button className="cm-scroll-top-btn" onClick={handleScrollTop} aria-label="Scroll to top" title="Scroll to top">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
            <path d="M9 14V4M4 9l5-5 5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
      )}
    </div>
    </DashboardLayout>
  );
}
