/**
 * Shared types for the Learning Cycle frontend shell (CB-TUTOR-002 #4069).
 *
 * These mirror the Phase-2 backend shapes targeted by #4067 (models) and
 * #4068 (prompts). Treat them as SHELL-ONLY contracts — real API bindings
 * land with the route PR (#TBD).
 */

export type CycleQuestionFormat =
  | 'multiple_choice'
  | 'true_false'
  | 'fill_blank';

export interface CycleQuestion {
  id: string;
  format: CycleQuestionFormat;
  question_text: string;
  /**
   * For multiple_choice: 4 options.
   * For true_false: ['True', 'False'].
   * For fill_blank: [canonical answer] (single-entry).
   */
  options: string[];
  correct_index: number;
  explanation: string;
  /**
   * Short re-teach snippet rendered on wrong answers. One per chunk, reused
   * across the 3-try loop.
   */
  reteach_snippet: string;
}

export interface CycleChunk {
  order: number;
  teach_content_md: string;
  questions: CycleQuestion[];
}

export type CycleSessionStatus =
  | 'in_progress'
  | 'completed'
  | 'abandoned';

export interface CycleSession {
  id: string;
  topic: string;
  status: CycleSessionStatus;
  chunks: CycleChunk[];
  current_chunk_idx: number;
}

export type CyclePhase = 'teach' | 'question' | 'feedback' | 'results';

/** Outcome for a single question (3-try loop). */
export interface CycleAnswerOutcome {
  questionId: string;
  attempts: number;
  correct: boolean;
  /** True when the user burned all 3 attempts without getting it right. */
  revealed: boolean;
  xp: number;
}

/** Aggregated per-chunk summary rendered on the results screen. */
export interface CycleChunkSummary {
  order: number;
  mastered: boolean;
  totalQuestions: number;
  correctQuestions: number;
}
