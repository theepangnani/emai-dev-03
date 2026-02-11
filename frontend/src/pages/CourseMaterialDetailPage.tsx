import { useState, useEffect, useCallback, lazy, Suspense } from 'react';
import { useParams, Link } from 'react-router-dom';
import { courseContentsApi, studyApi, type CourseContentItem, type StudyGuide } from '../api/client';
import { DashboardLayout } from '../components/DashboardLayout';
import { CreateTaskModal } from '../components/CreateTaskModal';
import { useConfirm } from '../components/ConfirmModal';
import './CourseMaterialDetailPage.css';

const MarkdownGuideBody = lazy(() =>
  import('react-markdown').then(mod => {
    const ReactMarkdown = mod.default;
    return import('remark-gfm').then(gfm => ({
      default: ({ content }: { content: string }) => (
        <ReactMarkdown remarkPlugins={[gfm.default]}>{content}</ReactMarkdown>
      ),
    }));
  })
);

type TabKey = 'document' | 'guide' | 'quiz' | 'flashcards';

export function CourseMaterialDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { confirm, confirmModal } = useConfirm();

  const [content, setContent] = useState<CourseContentItem | null>(null);
  const [guides, setGuides] = useState<StudyGuide[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>('document');
  const [generating, setGenerating] = useState<string | null>(null);

  // Quiz state
  const [quizIndex, setQuizIndex] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState<string | null>(null);
  const [showResult, setShowResult] = useState(false);
  const [quizScore, setQuizScore] = useState(0);
  const [, setQuizAnswers] = useState<Record<number, string>>({});
  const [quizFinished, setQuizFinished] = useState(false);

  // Flashcard state
  const [cardIndex, setCardIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);

  // Create task modal
  const [showTaskModal, setShowTaskModal] = useState(false);

  const contentId = parseInt(id || '0');

  const loadData = useCallback(async () => {
    if (!contentId) return;
    try {
      setError(null);
      const [cc, allGuides] = await Promise.all([
        courseContentsApi.get(contentId),
        studyApi.listGuides({ course_content_id: contentId }),
      ]);
      setContent(cc);
      setGuides(allGuides);
    } catch {
      setError('Failed to load course material');
    } finally {
      setLoading(false);
    }
  }, [contentId]);

  useEffect(() => { loadData(); }, [loadData]);

  const studyGuide = guides.find(g => g.guide_type === 'study_guide');
  const quiz = guides.find(g => g.guide_type === 'quiz');
  const flashcardSet = guides.find(g => g.guide_type === 'flashcards');

  const parsedQuiz = quiz ? (() => {
    try { return JSON.parse(quiz.content); } catch { return []; }
  })() : [];
  const parsedCards = flashcardSet ? (() => {
    try { return JSON.parse(flashcardSet.content); } catch { return []; }
  })() : [];

  const handleGenerate = async (type: 'study_guide' | 'quiz' | 'flashcards') => {
    if (!content) return;
    const labels = { study_guide: 'Study Guide', quiz: 'Practice Quiz', flashcards: 'Flashcards' };
    const ok = await confirm({
      title: `Generate ${labels[type]}`,
      message: `Generate a ${labels[type].toLowerCase()} from "${content.title}"? This will use AI credits.`,
      confirmLabel: 'Generate',
    });
    if (!ok) return;

    setGenerating(type);
    try {
      if (type === 'study_guide') {
        await studyApi.generateGuide({
          course_content_id: contentId,
          course_id: content.course_id,
          title: content.title,
          content: content.text_content || content.description || '',
        });
      } else if (type === 'quiz') {
        await studyApi.generateQuiz({
          course_content_id: contentId,
          course_id: content.course_id,
          topic: content.title,
          content: content.text_content || content.description || '',
          num_questions: 5,
        });
      } else {
        await studyApi.generateFlashcards({
          course_content_id: contentId,
          course_id: content.course_id,
          topic: content.title,
          content: content.text_content || content.description || '',
          num_cards: 10,
        });
      }
      await loadData();
      setActiveTab(type === 'study_guide' ? 'guide' : type);
    } catch {
      setError(`Failed to generate ${labels[type].toLowerCase()}`);
    } finally {
      setGenerating(null);
    }
  };

  const handleDeleteGuide = async (guide: StudyGuide) => {
    const ok = await confirm({
      title: 'Delete Study Material',
      message: `Delete "${guide.title}"? This cannot be undone.`,
      confirmLabel: 'Delete',
      variant: 'danger',
    });
    if (!ok) return;
    try {
      await studyApi.deleteGuide(guide.id);
      await loadData();
    } catch {
      setError('Failed to delete');
    }
  };

  // Quiz handlers
  const handleQuizAnswer = (answer: string) => {
    if (showResult) return;
    setSelectedAnswer(answer);
  };

  const handleQuizSubmit = () => {
    if (!selectedAnswer || !parsedQuiz[quizIndex]) return;
    const correct = parsedQuiz[quizIndex].correct_answer === selectedAnswer;
    if (correct) setQuizScore(s => s + 1);
    setQuizAnswers(prev => ({ ...prev, [quizIndex]: selectedAnswer }));
    setShowResult(true);
  };

  const handleQuizNext = () => {
    if (quizIndex < parsedQuiz.length - 1) {
      setQuizIndex(i => i + 1);
      setSelectedAnswer(null);
      setShowResult(false);
    } else {
      setQuizFinished(true);
    }
  };

  const resetQuiz = () => {
    setQuizIndex(0);
    setSelectedAnswer(null);
    setShowResult(false);
    setQuizScore(0);
    setQuizAnswers({});
    setQuizFinished(false);
  };

  if (loading) return <DashboardLayout><div className="cm-loading">Loading...</div></DashboardLayout>;
  if (error || !content) return (
    <DashboardLayout>
      <div className="cm-error">
        <p>{error || 'Content not found'}</p>
        <Link to="/course-materials" className="cm-back-link">Back to Course Materials</Link>
      </div>
    </DashboardLayout>
  );

  const tabs: { key: TabKey; label: string; hasContent: boolean }[] = [
    { key: 'document', label: 'Original Document', hasContent: !!(content.text_content || content.description) },
    { key: 'guide', label: 'Study Guide', hasContent: !!studyGuide },
    { key: 'quiz', label: 'Quiz', hasContent: !!quiz },
    { key: 'flashcards', label: 'Flashcards', hasContent: !!flashcardSet },
  ];

  return (
    <DashboardLayout>
      <div className="cm-detail-page">
        <div className="cm-detail-header">
          <Link to="/course-materials" className="cm-back-link">&larr; Back</Link>
          <div className="cm-detail-title-row">
            <h2>{content.title}</h2>
            {content.course_name && (
              <span className="cm-course-badge">{content.course_name}</span>
            )}
          </div>
          <div className="cm-detail-meta">
            <span className="cm-type-badge">{content.content_type}</span>
            <span>{new Date(content.created_at).toLocaleDateString()}</span>
            <button className="cm-action-btn" onClick={() => setShowTaskModal(true)} title="Create task">&#128203; + Task</button>
          </div>
        </div>

        {/* Tabs */}
        <div className="cm-tabs">
          {tabs.map(tab => (
            <button
              key={tab.key}
              className={`cm-tab${activeTab === tab.key ? ' active' : ''}${!tab.hasContent ? ' empty' : ''}`}
              onClick={() => setActiveTab(tab.key)}
            >
              {tab.label}
              {!tab.hasContent && tab.key !== 'document' && (
                <span className="cm-tab-empty-dot" />
              )}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="cm-tab-content">
          {activeTab === 'document' && (
            <div className="cm-document-tab">
              {content.text_content ? (
                <div className="cm-document-text">
                  <Suspense fallback={<div className="cm-render-loading">Rendering...</div>}>
                    <MarkdownGuideBody content={content.text_content} />
                  </Suspense>
                </div>
              ) : content.description ? (
                <p className="cm-document-desc">{content.description}</p>
              ) : (
                <p className="cm-empty-message">No document content available.</p>
              )}
              {content.reference_url && (
                <a href={content.reference_url} target="_blank" rel="noreferrer" className="cm-ref-link">
                  View Original Source
                </a>
              )}
            </div>
          )}

          {activeTab === 'guide' && (
            <div className="cm-guide-tab">
              {studyGuide ? (
                <>
                  <div className="cm-guide-actions">
                    <button className="cm-action-btn" onClick={() => window.print()} title="Print">Print</button>
                    <button className="cm-action-btn" onClick={() => handleGenerate('study_guide')} disabled={generating !== null}>Regenerate</button>
                    <button className="cm-action-btn danger" onClick={() => handleDeleteGuide(studyGuide)}>Delete</button>
                  </div>
                  <div className="cm-guide-body">
                    <Suspense fallback={<div className="cm-render-loading">Rendering...</div>}>
                      <MarkdownGuideBody content={studyGuide.content} />
                    </Suspense>
                  </div>
                </>
              ) : (
                <div className="cm-empty-tab">
                  <p>No study guide generated yet.</p>
                  <button
                    className="generate-btn"
                    onClick={() => handleGenerate('study_guide')}
                    disabled={generating !== null || !content.text_content}
                  >
                    {generating === 'study_guide' ? 'Generating...' : 'Generate Study Guide'}
                  </button>
                  {!content.text_content && (
                    <p className="cm-hint">Upload document content first to generate a study guide.</p>
                  )}
                </div>
              )}
            </div>
          )}

          {activeTab === 'quiz' && (
            <div className="cm-quiz-tab">
              {quiz && parsedQuiz.length > 0 ? (
                <>
                  <div className="cm-guide-actions">
                    <button className="cm-action-btn" onClick={resetQuiz}>Reset</button>
                    <button className="cm-action-btn" onClick={() => handleGenerate('quiz')} disabled={generating !== null}>Regenerate</button>
                    <button className="cm-action-btn danger" onClick={() => handleDeleteGuide(quiz)}>Delete</button>
                  </div>
                  {quizFinished ? (
                    <div className="cm-quiz-results">
                      <h3>Quiz Complete!</h3>
                      <div className="cm-quiz-score">
                        {quizScore} / {parsedQuiz.length}
                        <span className="cm-quiz-pct">
                          ({Math.round((quizScore / parsedQuiz.length) * 100)}%)
                        </span>
                      </div>
                      <button className="generate-btn" onClick={resetQuiz}>Try Again</button>
                    </div>
                  ) : (
                    <div className="cm-quiz-question">
                      <div className="cm-quiz-progress">
                        Question {quizIndex + 1} of {parsedQuiz.length}
                      </div>
                      <h3>{parsedQuiz[quizIndex].question}</h3>
                      <div className="cm-quiz-options">
                        {Object.entries(parsedQuiz[quizIndex].options || {}).map(([key, value]) => (
                          <button
                            key={key}
                            className={`cm-quiz-option${selectedAnswer === key ? ' selected' : ''}${
                              showResult && key === parsedQuiz[quizIndex].correct_answer ? ' correct' : ''
                            }${showResult && selectedAnswer === key && key !== parsedQuiz[quizIndex].correct_answer ? ' incorrect' : ''}`}
                            onClick={() => handleQuizAnswer(key)}
                            disabled={showResult}
                          >
                            <span className="cm-option-key">{key}</span>
                            <span>{value as string}</span>
                          </button>
                        ))}
                      </div>
                      {showResult && parsedQuiz[quizIndex].explanation && (
                        <div className="cm-quiz-explanation">
                          <strong>Explanation:</strong> {parsedQuiz[quizIndex].explanation}
                        </div>
                      )}
                      <div className="cm-quiz-actions">
                        {!showResult ? (
                          <button className="generate-btn" onClick={handleQuizSubmit} disabled={!selectedAnswer}>
                            Submit Answer
                          </button>
                        ) : (
                          <button className="generate-btn" onClick={handleQuizNext}>
                            {quizIndex < parsedQuiz.length - 1 ? 'Next Question' : 'See Results'}
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div className="cm-empty-tab">
                  <p>No quiz generated yet.</p>
                  <button
                    className="generate-btn"
                    onClick={() => handleGenerate('quiz')}
                    disabled={generating !== null || !content.text_content}
                  >
                    {generating === 'quiz' ? 'Generating...' : 'Generate Quiz'}
                  </button>
                  {!content.text_content && (
                    <p className="cm-hint">Upload document content first to generate a quiz.</p>
                  )}
                </div>
              )}
            </div>
          )}

          {activeTab === 'flashcards' && (
            <div className="cm-flashcards-tab">
              {flashcardSet && parsedCards.length > 0 ? (
                <>
                  <div className="cm-guide-actions">
                    <button className="cm-action-btn" onClick={() => { setCardIndex(0); setIsFlipped(false); }}>Reset</button>
                    <button className="cm-action-btn" onClick={() => {
                      setCardIndex(0);
                      setIsFlipped(false);
                    }}>Shuffle</button>
                    <button className="cm-action-btn" onClick={() => handleGenerate('flashcards')} disabled={generating !== null}>Regenerate</button>
                    <button className="cm-action-btn danger" onClick={() => handleDeleteGuide(flashcardSet)}>Delete</button>
                  </div>
                  <div className="cm-flashcard-progress">
                    Card {cardIndex + 1} of {parsedCards.length}
                  </div>
                  <div
                    className={`cm-flashcard${isFlipped ? ' flipped' : ''}`}
                    onClick={() => setIsFlipped(f => !f)}
                  >
                    <div className="cm-flashcard-inner">
                      <div className="cm-flashcard-front">
                        <p>{parsedCards[cardIndex]?.front}</p>
                      </div>
                      <div className="cm-flashcard-back">
                        <p>{parsedCards[cardIndex]?.back}</p>
                      </div>
                    </div>
                  </div>
                  <div className="cm-flashcard-controls">
                    <button
                      className="cm-action-btn"
                      onClick={() => { setCardIndex(i => i - 1); setIsFlipped(false); }}
                      disabled={cardIndex === 0}
                    >
                      Previous
                    </button>
                    <button
                      className="cm-action-btn"
                      onClick={() => { setCardIndex(i => i + 1); setIsFlipped(false); }}
                      disabled={cardIndex >= parsedCards.length - 1}
                    >
                      Next
                    </button>
                  </div>
                  <p className="cm-hint">Click card to flip. Use arrow keys to navigate.</p>
                </>
              ) : (
                <div className="cm-empty-tab">
                  <p>No flashcards generated yet.</p>
                  <button
                    className="generate-btn"
                    onClick={() => handleGenerate('flashcards')}
                    disabled={generating !== null || !content.text_content}
                  >
                    {generating === 'flashcards' ? 'Generating...' : 'Generate Flashcards'}
                  </button>
                  {!content.text_content && (
                    <p className="cm-hint">Upload document content first to generate flashcards.</p>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {generating && (
          <div className="cm-generating-overlay">
            <div className="cm-generating-spinner" />
            <p>Generating... This may take a moment.</p>
          </div>
        )}
      </div>
      <CreateTaskModal
        open={showTaskModal}
        onClose={() => setShowTaskModal(false)}
        prefillTitle={`Review: ${content.title}`}
        courseId={content.course_id}
        courseContentId={content.id}
        linkedEntityLabel={`${content.title}${content.course_name ? ` (${content.course_name})` : ''}`}
      />
      {confirmModal}
    </DashboardLayout>
  );
}
