/**
 * CB-LAND-001 §6.136.1 §5 — How It Works step definitions.
 *
 * Four steps, rendered as an accordion by
 * `HowItWorksAccordion.tsx` with a synced preview pane on the right.
 */

export type HowItWorksStep = {
  /** Stable id, used for aria-controls / aria-labelledby wiring. */
  id: 'connect' | 'organize' | 'practice' | 'digest';
  /** Step number shown in the accordion row (1-indexed). */
  number: number;
  /** Accordion row title. */
  title: string;
  /** One-line collapsed summary. */
  summary: string;
  /** Expanded paragraph copy shown on the active row. */
  body: string;
  /** Short label for the preview pane mock. */
  previewLabel: string;
};

export const howItWorksSteps: readonly HowItWorksStep[] = [
  {
    id: 'connect',
    number: 1,
    title: 'Connect',
    summary: 'Link Google Classroom, Gmail, or upload a file.',
    body: 'Bring in course content from Google Classroom, forward teacher emails to your ClassBridge inbox, or upload a PDF or image. Everything stays private to your family.',
    previewLabel: 'Connect sources',
  },
  {
    id: 'organize',
    number: 2,
    title: 'AI organizes everything',
    summary: 'Structured notes, tagged by subject.',
    body: 'ClassBridge turns raw content into clean notes, tagged by subject and topic, ready for review. No more scrolling through a dozen tabs to find tonight\u2019s homework.',
    previewLabel: 'Organized notebook',
  },
  {
    id: 'practice',
    number: 3,
    title: 'Student practices with Flash Tutor',
    summary: 'Adaptive Q&A that meets them at their level.',
    body: 'Flash Tutor generates flashcards and quiz questions from the student\u2019s own notes, then adapts difficulty as they go. Learning science meets the kitchen-table study session.',
    previewLabel: 'Flash Tutor card',
  },
  {
    id: 'digest',
    number: 4,
    title: 'Parents stay in the loop',
    summary: 'Daily digest: what was assigned, what\u2019s due, how they did.',
    body: 'A short daily email summarizes the day\u2019s homework, upcoming deadlines, and practice progress \u2014 so you can help without hovering.',
    previewLabel: 'Parent digest email',
  },
] as const;
