import type { DemoType } from '../../api/demo';

/**
 * Pre-loaded Grade 8 science sample + demo-type defaults for the Instant
 * Trial modal. Kept in a sibling module so the modal file stays under
 * 200 lines.
 */

export const SAMPLE_TITLE = 'Grade 8 Science — Cells and Systems';

export const SAMPLE_TEXT = `Grade 8 Science — Cells and Systems

Living things are made of cells. A cell is the smallest unit of life that can carry out all the processes needed to stay alive. Plant cells have a cell wall and chloroplasts that let them capture sunlight and turn it into food through a process called photosynthesis. Animal cells do not have chloroplasts; they get energy by eating plants or other animals.

Cells are organized into tissues, tissues into organs, and organs into systems. The digestive system, for example, breaks down food so the body can use the nutrients. The respiratory system moves oxygen into the blood and carbon dioxide out of it. The circulatory system then carries blood — with oxygen and nutrients — to every cell and carries waste away.

Key terms to remember: cell, tissue, organ, organ system, photosynthesis, respiration, and homeostasis (how the body keeps its internal conditions steady, like temperature).`;

export const TABS: { id: DemoType; label: string }[] = [
  { id: 'ask', label: 'Ask' },
  { id: 'study_guide', label: 'Study Guide' },
  { id: 'flash_tutor', label: 'Flash Tutor' },
];

export const DEFAULT_QUESTIONS: Record<DemoType, string> = {
  ask: 'Can you explain photosynthesis in a way a Grade 8 student would understand?',
  study_guide: 'Make a short study guide from this reading.',
  flash_tutor: 'Quiz me with 3 questions from this reading.',
};

/** Roughly count words in a string — good enough for the ≤500 word UI guard. */
export function countWords(text: string): number {
  const trimmed = text.trim();
  if (!trimmed) return 0;
  return trimmed.split(/\s+/).length;
}
