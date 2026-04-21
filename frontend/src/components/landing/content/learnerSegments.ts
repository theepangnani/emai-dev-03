/**
 * CB-LAND-001 S9 — Learner-segment tab content.
 *
 * Data-driven source for the "One platform. Every role." segment tabs section
 * of the landing v2 redesign (#3809 / §6.136.1 §9). Five audience tabs with a
 * left-stack + right-detail layout; Private Tutors is a Phase 4 teaser.
 *
 * Content is ClassBridge-accurate — do not swap in Mindgrasp copy.
 *
 * Reference: docs/design/landing-v2-reference/10-learner-segments.png
 */

export type LearnerSegmentId =
  | 'parents'
  | 'students'
  | 'teachers'
  | 'admins'
  | 'private-tutors';

export interface LearnerSegment {
  /** Stable id — drives tab / panel aria ids and React keys. */
  id: LearnerSegmentId;
  /** Tab button title (e.g. "Parents"). */
  title: string;
  /** Tab button subtitle (bulleted audience hint). */
  subtitle: string;
  /** Right-panel role title (larger, serif headline). */
  roleTitle: string;
  /** Right-panel 2-3 sentence description. */
  description: string;
  /** 4-6 short checklist bullets. */
  bullets: string[];
  /** Phase 4 teaser — renders a "Coming Phase 4" pill on the tab. */
  comingPhase4?: boolean;
}

export const learnerSegments: LearnerSegment[] = [
  {
    id: 'parents',
    title: 'Parents',
    subtitle: 'Daily digest · Multi-child view',
    roleTitle: 'Parents',
    description:
      "Stay in the loop without digging through portals. ClassBridge summarises every child's week, flags what needs attention, and gives you one place to message teachers.",
    bullets: [
      'Daily email digest',
      "See every child's progress",
      'Message teachers',
      'Manage tasks for the family',
    ],
  },
  {
    id: 'students',
    title: 'Students',
    subtitle: 'AI study tools · All classes',
    roleTitle: 'Students',
    description:
      'Turn course material into study guides, flashcards, and quick practice sessions. Keep every class, task, and deadline in one place so nothing slips.',
    bullets: [
      'AI study guides',
      'Flash Tutor practice',
      'Task reminders',
      'All classes in one place',
    ],
  },
  {
    id: 'teachers',
    title: 'Teachers',
    subtitle: 'Resource extraction · Announcements',
    roleTitle: 'Teachers',
    description:
      'Auto-extract resource links from your Google Classroom materials, spot students who need help, and send one-tap announcements — without leaving your workflow.',
    bullets: [
      'Auto-extracted resource links',
      'Student alerts',
      'One-tap announcements',
      'Sync with Google Classroom',
    ],
  },
  {
    id: 'admins',
    title: 'Admins',
    subtitle: 'Platform health · Audit logs',
    roleTitle: 'Admins',
    description:
      'Monitor platform health, review audit logs, and broadcast across the district. Role-based access keeps the right people in the right dashboards.',
    bullets: [
      'Platform health dashboard',
      'Audit logs',
      'Broadcast messaging',
      'User management',
    ],
  },
  {
    id: 'private-tutors',
    title: 'Private Tutors',
    subtitle: 'Marketplace · Booking · Billing',
    roleTitle: 'Private Tutors',
    description:
      'A marketplace for independent tutors — discoverable profiles, parent-driven booking, and session billing. Shipping with ClassBridge Phase 4.',
    bullets: [
      'Marketplace profile',
      'Booking',
      'Parent messaging',
      'Session billing',
    ],
    comingPhase4: true,
  },
];
