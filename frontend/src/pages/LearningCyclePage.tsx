/**
 * LearningCyclePage — /tutor/cycle/:id shell (CB-TUTOR-002 Phase 2 #4069).
 *
 * This is the FRONTEND SHELL ONLY. Phase-2 backend endpoints — #4067
 * (models), #4068 (prompts), and the upcoming routes PR — are not wired
 * yet, so this page:
 *
 *   1. Renders behind the `learning_cycle_enabled` feature flag (kill-switch).
 *   2. Uses a local mock session to prove the component composition works.
 *   3. Exposes enough shape (types.ts) for the route PR to drop in a real
 *      fetch without re-working the page.
 *
 * Interaction model (stubbed):
 *   teach → question → feedback(correct|retry|reveal) → next question or
 *   next chunk → results. All transitions are local state — no API calls.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { DashboardLayout } from '../components/DashboardLayout';
import { useFeatureFlagEnabled } from '../hooks/useFeatureToggle';
import {
  CycleFeedback,
  CycleProgress,
  CycleQuestion,
  CycleResults,
  CycleTeachBlock,
} from '../components/cycle';
import type {
  CycleAnswerOutcome,
  CycleChunkSummary,
  CycleFeedbackVerdict,
  CyclePhase,
  CycleSession,
} from '../components/cycle';
import '../components/cycle/cycle.css';

/** XP tiers: first try, second try, third try, revealed. */
const XP_BY_ATTEMPT = [30, 15, 5, 0] as const;

function xpForAttempts(attempts: number, correct: boolean): number {
  if (!correct) return XP_BY_ATTEMPT[3];
  const i = Math.min(Math.max(attempts - 1, 0), XP_BY_ATTEMPT.length - 1);
  return XP_BY_ATTEMPT[i];
}

/**
 * Mock session used by the shell. Replaced by a real
 * `useQuery(['cycle-session', id], …)` call in the route PR.
 */
const MOCK_SESSION: CycleSession = {
  id: 'mock',
  topic: 'Fractions',
  status: 'in_progress',
  current_chunk_idx: 0,
  chunks: [
    {
      order: 0,
      teach_content_md:
        'A **fraction** represents a part of a whole. The bottom number (**denominator**) tells you how many equal pieces the whole is split into. The top number (**numerator**) tells you how many of those pieces you have.\n\nFor example, in **3/4**, the denominator is 4 (four equal pieces) and the numerator is 3 (you have three of them).',
      questions: [
        {
          id: 'q0-0',
          format: 'multiple_choice',
          question_text: 'In the fraction 5/8, which number is the denominator?',
          options: ['5', '8', '13', '3'],
          correct_index: 1,
          explanation:
            'The denominator sits below the line and tells you how many equal pieces make up the whole — here, 8.',
          reteach_snippet:
            'Denominator = bottom number. It counts the total equal pieces in the whole.',
        },
        {
          id: 'q0-1',
          format: 'true_false',
          question_text:
            'True or False: The numerator is the number on top of a fraction.',
          options: ['True', 'False'],
          correct_index: 0,
          explanation:
            'Correct — numerator is on top, denominator is on the bottom.',
          reteach_snippet:
            '"Numerator" = Number on top. "Denominator" = Down below.',
        },
        {
          id: 'q0-2',
          format: 'fill_blank',
          question_text:
            'The bottom number of a fraction is called the ____.',
          options: ['denominator'],
          correct_index: 0,
          explanation:
            'The denominator describes how many equal parts the whole is cut into.',
          reteach_snippet:
            'Hint: it starts with "d" and lives at the Downstairs of the fraction.',
        },
      ],
    },
    {
      order: 1,
      teach_content_md:
        'To **add fractions with the same denominator**, you only add the **numerators**. Keep the denominator the same.\n\nExample: 1/5 + 2/5 = **3/5**. The denominator stays at 5 because the "piece size" hasn\'t changed — we just have more of the same pieces.',
      questions: [
        {
          id: 'q1-0',
          format: 'multiple_choice',
          question_text: 'What is 2/7 + 3/7?',
          options: ['5/14', '5/7', '6/7', '1/7'],
          correct_index: 1,
          explanation:
            'Add only the numerators (2 + 3 = 5). The denominator stays 7 because the pieces are the same size.',
          reteach_snippet:
            'Same-denominator rule: add tops, keep bottom.',
        },
        {
          id: 'q1-1',
          format: 'true_false',
          question_text:
            'True or False: When adding 1/6 + 2/6, you should also add the denominators.',
          options: ['True', 'False'],
          correct_index: 1,
          explanation:
            'False — denominators stay the same when they already match. Only numerators add.',
          reteach_snippet:
            'Matching denominators → add tops only, leave the bottom alone.',
        },
        {
          id: 'q1-2',
          format: 'fill_blank',
          question_text: '4/9 + 3/9 = ____',
          options: ['7/9'],
          correct_index: 0,
          explanation:
            '4 + 3 = 7, and the denominator 9 is unchanged. So the answer is 7/9.',
          reteach_snippet:
            'Add numerators (4 + 3), keep the denominator (9).',
        },
      ],
    },
  ],
};

export function LearningCyclePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const enabled = useFeatureFlagEnabled('learning_cycle_enabled');

  // Kill-switch: feature flag guards this whole page. When the flag is off,
  // bounce back to the unified tutor. The route PR can swap this for a
  // richer gated state once copy is agreed.
  if (!enabled) {
    return <Navigate to="/tutor" replace />;
  }

  return <LearningCycleShell sessionId={id ?? 'mock'} onExit={() => navigate('/tutor')} />;
}

interface LearningCycleShellProps {
  sessionId: string;
  onExit: () => void;
}

function LearningCycleShell({ sessionId, onExit }: LearningCycleShellProps) {
  // Shell uses the mock until the real session API lands. The ID is
  // accepted so deep-links like /tutor/cycle/42 don't break when the API
  // flips on.
  const session = useMemo<CycleSession>(() => ({ ...MOCK_SESSION, id: sessionId }), [sessionId]);

  const [chunkIdx, setChunkIdx] = useState(session.current_chunk_idx);
  const [questionIdx, setQuestionIdx] = useState(0);
  const [phase, setPhase] = useState<CyclePhase>('teach');
  const [attempt, setAttempt] = useState(0);
  const [verdict, setVerdict] = useState<CycleFeedbackVerdict>('retry');
  const [lastXp, setLastXp] = useState(0);
  const [outcomes, setOutcomes] = useState<CycleAnswerOutcome[]>([]);

  const chunk = session.chunks[chunkIdx];
  const question = chunk?.questions[questionIdx];
  const accentClass = `cycle-accent-${(chunkIdx % 4) + 1}`;

  // Reset per-question transient state when the question pointer changes.
  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect -- intentional reset on question change */
    setAttempt(0);
    setVerdict('retry');
    setLastXp(0);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [chunkIdx, questionIdx]);

  const handleReadyForQuestions = useCallback(() => {
    setPhase('question');
  }, []);

  const handleAnswer = useCallback(
    (payload: { index?: number; text?: string }) => {
      if (!question) return;
      const nextAttempts = attempt + 1;
      const canonical = question.options[question.correct_index] ?? '';
      const correct =
        payload.index !== undefined
          ? payload.index === question.correct_index
          : !!payload.text &&
            payload.text.trim().toLowerCase() === canonical.trim().toLowerCase();

      if (correct) {
        const xp = xpForAttempts(nextAttempts, true);
        setLastXp(xp);
        setVerdict('correct');
        setOutcomes((prev) => [
          ...prev,
          {
            questionId: question.id,
            attempts: nextAttempts,
            correct: true,
            revealed: false,
            xp,
          },
        ]);
      } else if (nextAttempts >= 3) {
        setLastXp(0);
        setVerdict('reveal');
        setOutcomes((prev) => [
          ...prev,
          {
            questionId: question.id,
            attempts: nextAttempts,
            correct: false,
            revealed: true,
            xp: 0,
          },
        ]);
      } else {
        setVerdict('retry');
      }
      setAttempt(nextAttempts);
      setPhase('feedback');
    },
    [attempt, question],
  );

  const handleFeedbackContinue = useCallback(() => {
    // "Try again" path — stay on the same question, bump back to the
    // question phase. The attempt counter already moved forward in
    // handleAnswer so the UI shows "Attempt 2 of 3".
    if (verdict === 'retry') {
      setPhase('question');
      return;
    }
    // Either we got it right (correct) or we burned all 3 (reveal). Either
    // way, advance the pointer.
    const hasMoreQuestions = questionIdx + 1 < (chunk?.questions.length ?? 0);
    if (hasMoreQuestions) {
      setQuestionIdx((i) => i + 1);
      setPhase('question');
      return;
    }
    const hasMoreChunks = chunkIdx + 1 < session.chunks.length;
    if (hasMoreChunks) {
      setChunkIdx((i) => i + 1);
      setQuestionIdx(0);
      setPhase('teach');
      return;
    }
    setPhase('results');
  }, [verdict, questionIdx, chunk, chunkIdx, session.chunks.length]);

  // Derive chunk-level summaries for the results screen.
  const chunkSummaries = useMemo<CycleChunkSummary[]>(() => {
    return session.chunks.map((c) => {
      const chunkOutcomes = outcomes.filter((o) =>
        c.questions.some((q) => q.id === o.questionId),
      );
      const correctCount = chunkOutcomes.filter((o) => o.correct).length;
      return {
        order: c.order,
        totalQuestions: c.questions.length,
        correctQuestions: correctCount,
        mastered:
          chunkOutcomes.length === c.questions.length &&
          correctCount === c.questions.length,
      };
    });
  }, [session.chunks, outcomes]);

  const totalXp = outcomes.reduce((sum, o) => sum + o.xp, 0);
  const attemptedCount = outcomes.length;
  const correctCount = outcomes.filter((o) => o.correct).length;
  const accuracy = attemptedCount === 0 ? 0 : correctCount / attemptedCount;
  const completedChunks = chunkSummaries.filter((c) => c.mastered).length;

  return (
    <DashboardLayout>
      <div className="cycle-shell">
        <header>
          <p className="cycle-shell__topic">Learning cycle</p>
          <h1 className="cycle-shell__heading">{session.topic}</h1>
        </header>

        <CycleProgress
          total={session.chunks.length}
          currentIndex={chunkIdx}
          completed={completedChunks}
        />

        <div className="cycle-shell__stage" key={`${chunkIdx}-${questionIdx}-${phase}`}>
          {phase === 'teach' && chunk && (
            <CycleTeachBlock
              chunk={chunk}
              index={chunkIdx + 1}
              total={session.chunks.length}
              onReady={handleReadyForQuestions}
              accentClass={accentClass}
            />
          )}

          {phase === 'question' && question && (
            <div className={accentClass}>
              <CycleQuestion
                question={question}
                attempt={attempt}
                onAnswer={handleAnswer}
              />
            </div>
          )}

          {phase === 'feedback' && question && (
            <div className={accentClass}>
              <CycleFeedback
                verdict={verdict}
                question={question}
                xp={lastXp}
                onContinue={handleFeedbackContinue}
              />
            </div>
          )}

          {phase === 'results' && (
            <CycleResults
              topic={session.topic}
              totalXp={totalXp}
              accuracy={accuracy}
              chunkSummaries={chunkSummaries}
              onDrillMore={onExit}
              onNewTopic={onExit}
            />
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}

export default LearningCyclePage;
