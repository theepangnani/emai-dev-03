/**
 * CB-LAND-001 S5 — Feature row content.
 *
 * Data-driven source for the 6 alternating pastel feature rows on the §4
 * "Every signal" section of the landing v2 redesign (#3805 / §6.136.1).
 *
 * Ordering is authoritative here — rows render in array order, alternating
 * text-left / text-right layout based on index. Backgrounds cycle through the
 * `variant` prop which maps to `--color-row-{variant}` tokens from S1.
 *
 * Reference: docs/design/landing-v2-reference/04a-feature-rows-notes-summary.png
 * (+ 04b, 04c). Do not reorder without updating the reference notes.
 */

export type FeatureRowVariant = 'peach' | 'mint' | 'lavender' | 'pink';

export interface FeatureRowContent {
  /** Stable id — used as React key and for section anchors. */
  id: string;
  /** Short eyebrow label (e.g. "AI Study Guides"). Rendered above headline. */
  kicker: string;
  /**
   * Headline HTML string with a single `<em>` accent (serif-italic) wrapped
   * around the punchy phrase. Sanitised at render — only `<em>` is honoured.
   */
  headlineHtml: string;
  /** 3-line body copy. Rendered as a single `<p>` with line-height. */
  body: string;
  /** Text for the "Learn more" link. Link target set in FeatureRow. */
  learnMoreLabel: string;
  /** Screenshot placeholder label (used until real screenshots land). */
  screenshotLabel: string;
  /** Pastel row variant — cycles peach / mint / pink / lavender / peach / mint. */
  variant: FeatureRowVariant;
}

export const features: FeatureRowContent[] = [
  {
    id: 'ai-study-guides',
    kicker: 'AI Study Guides',
    headlineHtml: 'Notes that <em>write themselves.</em>',
    body:
      'Drop in a PDF, slide deck, or textbook chapter and ClassBridge returns a ' +
      'structured study guide with summaries, key terms, and worked examples — ' +
      'ready to review in minutes, not hours.',
    learnMoreLabel: 'Learn more',
    screenshotLabel: 'Screenshot: AI Study Guide output',
    variant: 'peach',
  },
  {
    id: 'flash-tutor',
    kicker: 'Flash Tutor',
    headlineHtml: 'Practice that <em>sticks.</em>',
    body:
      'Bite-size tutoring sessions that adapt to what a student just got wrong. ' +
      'Flash Tutor re-teaches the exact concept, then loops back 24 hours later ' +
      'to lock it in — built on spaced-repetition research.',
    learnMoreLabel: 'Learn more',
    screenshotLabel: 'Screenshot: Flash Tutor session',
    variant: 'mint',
  },
  {
    id: 'adaptive-quizzes',
    kicker: 'Adaptive Quizzes + Flashcards',
    headlineHtml: 'Spot gaps <em>before</em> the exam does.',
    body:
      'Auto-generated quizzes and flashcards tuned to the student\u2019s live ' +
      'mastery curve. Every wrong answer narrows the next question — so study ' +
      'time compounds instead of repeating what they already know.',
    learnMoreLabel: 'Learn more',
    screenshotLabel: 'Screenshot: Adaptive quiz results',
    variant: 'pink',
  },
  {
    id: 'parent-email-digest',
    kicker: 'Parent Email Digest',
    headlineHtml: 'Every school email, <em>summarized daily.</em>',
    body:
      'We read the teacher newsletters, board bulletins, and field-trip notices ' +
      'so you don\u2019t have to. Parents get one calm daily digest with action ' +
      'items, deadlines, and the kid-specific bits highlighted.',
    learnMoreLabel: 'Learn more',
    screenshotLabel: 'Screenshot: Parent Email Digest',
    variant: 'lavender',
  },
  {
    id: 'classroom-board-integration',
    kicker: 'Google Classroom + Board Integration',
    headlineHtml: 'Your school data, <em>unified.</em>',
    body:
      'Google Classroom assignments, board announcements, and teacher emails ' +
      'flow into one feed. The Tuesday Mirror stitches them together so nothing ' +
      'slips between platforms — or between parents.',
    learnMoreLabel: 'Learn more',
    screenshotLabel: 'Screenshot: Tuesday Mirror unified feed',
    variant: 'peach',
  },
  {
    id: 'parent-teacher-messaging',
    kicker: 'Parent-Teacher Messaging with AI',
    headlineHtml: 'Real conversations, <em>smart summaries.</em>',
    body:
      'Direct parent\u2013teacher messaging with an AI assist that drafts the ' +
      'tone, flags urgency, and summarises long threads. Teachers save hours; ' +
      'parents get answers faster.',
    learnMoreLabel: 'Learn more',
    screenshotLabel: 'Screenshot: Parent-Teacher Messaging thread',
    variant: 'mint',
  },
];
