import type { TourStep } from '../OnboardingTour';

/** Tutorial key constants — must match backend step names */
export const TUTORIAL_KEYS = {
  PARENT_DASHBOARD: 'parent_dashboard',
  STUDENT_DASHBOARD: 'student_dashboard',
  TEACHER_DASHBOARD: 'teacher_dashboard',
} as const;

export const PARENT_TUTORIAL_STEPS: TourStep[] = [
  {
    target: '.sidebar-nav .sidebar-link:nth-child(2)',
    title: 'Add Your Child',
    content: 'Start by adding your child to ClassBridge. You can link them to your account and manage their classes.',
    position: 'right',
    journeyId: 'P02',
  },
  {
    target: '.sidebar-nav .sidebar-link:nth-child(3)',
    title: 'Create a Course',
    content: 'Create classes for your child or sync from Google Classroom to import existing ones.',
    position: 'right',
    journeyId: 'P10',
  },
  {
    target: '.sidebar-nav .sidebar-link:nth-child(4)',
    title: 'Generate Study Guide',
    content: 'Upload class materials and let AI generate study guides, flashcards, and quizzes.',
    position: 'right',
    journeyId: 'P03',
  },
  {
    target: '.sidebar-nav .sidebar-link:nth-child(5)',
    title: 'Create a Task',
    content: 'Assign tasks to your child with due dates and track their completion.',
    position: 'right',
    journeyId: 'P07',
  },
];

export const STUDENT_TUTORIAL_STEPS: TourStep[] = [
  {
    target: '.sidebar-nav .sidebar-link:nth-child(2)',
    title: 'View Your Courses',
    content: 'See all your classes synced from Google Classroom or added by your parent.',
    position: 'right',
    journeyId: 'S01',
  },
  {
    target: '.sidebar-nav .sidebar-link:nth-child(3)',
    title: 'Open Study Materials',
    content: 'Access AI-generated study guides, flashcards, and summaries for your classes.',
    position: 'right',
    journeyId: 'S02',
  },
  {
    target: '.sidebar-nav .sidebar-link:nth-child(4)',
    title: 'Take a Quiz',
    content: 'Test your knowledge with AI-generated quizzes and track your scores over time.',
    position: 'right',
    journeyId: 'S03',
  },
];

export const TEACHER_TUTORIAL_STEPS: TourStep[] = [
  {
    target: '.sidebar-nav .sidebar-link:nth-child(2)',
    title: 'Sync Google Classroom',
    content: 'Connect your Google account to import your classes and student rosters automatically.',
    position: 'right',
    journeyId: 'T02',
  },
  {
    target: '.sidebar-nav .sidebar-link:nth-child(3)',
    title: 'View Students',
    content: 'See all students across your classes and their progress.',
    position: 'right',
    journeyId: 'T02',
  },
  {
    target: '.sidebar-nav .sidebar-link:last-child',
    title: 'Send Messages',
    content: 'Communicate with parents directly through ClassBridge or monitor synced emails.',
    position: 'right',
    journeyId: 'T05',
  },
];
