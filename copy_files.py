import shutil
import os

BASE = 'c:/dev/emai/class-bridge-phase-2/.claude/worktrees'
MAIN = 'c:/dev/emai/class-bridge-phase-2'

copies = [
    # Models
    ('agent-a78aca00/app/models/student_goal.py', 'app/models/student_goal.py'),
    ('agent-a61e2e1f/app/models/homework_help.py', 'app/models/homework_help.py'),
    ('agent-a3651fa6/app/models/attendance.py', 'app/models/attendance.py'),
    ('agent-ad0f3499/app/models/wellness.py', 'app/models/wellness.py'),
    ('agent-aceb5196/app/models/gamification.py', 'app/models/gamification.py'),
    ('agent-a04b4dec/app/models/newsletter.py', 'app/models/newsletter.py'),
    ('agent-a59b1068/app/models/meeting_scheduler.py', 'app/models/meeting_scheduler.py'),
    ('agent-af1ba60b/app/models/lesson_summary.py', 'app/models/lesson_summary.py'),
    ('agent-a8217a7b/app/models/learning_journal.py', 'app/models/learning_journal.py'),
    # Schemas
    ('agent-a3cc71fc/app/schemas/peer_review.py', 'app/schemas/peer_review.py'),
    ('agent-a78aca00/app/schemas/student_goal.py', 'app/schemas/student_goal.py'),
    ('agent-a61e2e1f/app/schemas/homework_help.py', 'app/schemas/homework_help.py'),
    ('agent-a3651fa6/app/schemas/attendance.py', 'app/schemas/attendance.py'),
    ('agent-ad0f3499/app/schemas/wellness.py', 'app/schemas/wellness.py'),
    ('agent-aceb5196/app/schemas/gamification.py', 'app/schemas/gamification.py'),
    ('agent-a04b4dec/app/schemas/newsletter.py', 'app/schemas/newsletter.py'),
    ('agent-a59b1068/app/schemas/meeting_scheduler.py', 'app/schemas/meeting_scheduler.py'),
    ('agent-af1ba60b/app/schemas/lesson_summary.py', 'app/schemas/lesson_summary.py'),
    ('agent-a8217a7b/app/schemas/learning_journal.py', 'app/schemas/learning_journal.py'),
    # Services
    ('agent-a3cc71fc/app/services/peer_review.py', 'app/services/peer_review.py'),
    ('agent-a78aca00/app/services/student_goal.py', 'app/services/student_goal.py'),
    ('agent-a61e2e1f/app/services/homework_help.py', 'app/services/homework_help.py'),
    ('agent-a3651fa6/app/services/attendance.py', 'app/services/attendance.py'),
    ('agent-ad0f3499/app/services/wellness.py', 'app/services/wellness.py'),
    ('agent-aceb5196/app/services/gamification.py', 'app/services/gamification.py'),
    ('agent-a04b4dec/app/services/newsletter_service.py', 'app/services/newsletter_service.py'),
    ('agent-a59b1068/app/services/meeting_scheduler.py', 'app/services/meeting_scheduler.py'),
    ('agent-af1ba60b/app/services/lesson_summary.py', 'app/services/lesson_summary.py'),
    ('agent-a8217a7b/app/services/learning_journal.py', 'app/services/learning_journal.py'),
    # Routes
    ('agent-a3cc71fc/app/api/routes/peer_review.py', 'app/api/routes/peer_review.py'),
    ('agent-a78aca00/app/api/routes/student_goals.py', 'app/api/routes/student_goals.py'),
    ('agent-a61e2e1f/app/api/routes/homework_help.py', 'app/api/routes/homework_help.py'),
    ('agent-a3651fa6/app/api/routes/attendance.py', 'app/api/routes/attendance.py'),
    ('agent-ad0f3499/app/api/routes/wellness.py', 'app/api/routes/wellness.py'),
    ('agent-aceb5196/app/api/routes/gamification.py', 'app/api/routes/gamification.py'),
    ('agent-a04b4dec/app/api/routes/newsletters.py', 'app/api/routes/newsletters.py'),
    ('agent-a59b1068/app/api/routes/meeting_scheduler.py', 'app/api/routes/meeting_scheduler.py'),
    ('agent-af1ba60b/app/api/routes/lesson_summary.py', 'app/api/routes/lesson_summary.py'),
    ('agent-a8217a7b/app/api/routes/learning_journal.py', 'app/api/routes/learning_journal.py'),
    # Frontend API files
    ('agent-a3cc71fc/frontend/src/api/peerReview.ts', 'frontend/src/api/peerReview.ts'),
    ('agent-a78aca00/frontend/src/api/studentGoals.ts', 'frontend/src/api/studentGoals.ts'),
    ('agent-a61e2e1f/frontend/src/api/homeworkHelp.ts', 'frontend/src/api/homeworkHelp.ts'),
    ('agent-a3651fa6/frontend/src/api/attendance.ts', 'frontend/src/api/attendance.ts'),
    ('agent-ad0f3499/frontend/src/api/wellness.ts', 'frontend/src/api/wellness.ts'),
    ('agent-aceb5196/frontend/src/api/gamification.ts', 'frontend/src/api/gamification.ts'),
    ('agent-a04b4dec/frontend/src/api/newsletters.ts', 'frontend/src/api/newsletters.ts'),
    ('agent-a59b1068/frontend/src/api/meetingScheduler.ts', 'frontend/src/api/meetingScheduler.ts'),
    ('agent-af1ba60b/frontend/src/api/lessonSummary.ts', 'frontend/src/api/lessonSummary.ts'),
    ('agent-a8217a7b/frontend/src/api/learningJournal.ts', 'frontend/src/api/learningJournal.ts'),
    # Frontend pages
    ('agent-a3cc71fc/frontend/src/pages/PeerReviewPage.tsx', 'frontend/src/pages/PeerReviewPage.tsx'),
    ('agent-a3cc71fc/frontend/src/pages/PeerReviewPage.css', 'frontend/src/pages/PeerReviewPage.css'),
    ('agent-a78aca00/frontend/src/pages/StudentGoalsPage.tsx', 'frontend/src/pages/StudentGoalsPage.tsx'),
    ('agent-a78aca00/frontend/src/pages/StudentGoalsPage.css', 'frontend/src/pages/StudentGoalsPage.css'),
    ('agent-a61e2e1f/frontend/src/pages/HomeworkHelperPage.tsx', 'frontend/src/pages/HomeworkHelperPage.tsx'),
    ('agent-a61e2e1f/frontend/src/pages/HomeworkHelperPage.css', 'frontend/src/pages/HomeworkHelperPage.css'),
    ('agent-a3651fa6/frontend/src/pages/AttendancePage.tsx', 'frontend/src/pages/AttendancePage.tsx'),
    ('agent-a3651fa6/frontend/src/pages/AttendancePage.css', 'frontend/src/pages/AttendancePage.css'),
    ('agent-ad0f3499/frontend/src/pages/WellnessPage.tsx', 'frontend/src/pages/WellnessPage.tsx'),
    ('agent-ad0f3499/frontend/src/pages/WellnessPage.css', 'frontend/src/pages/WellnessPage.css'),
    ('agent-aceb5196/frontend/src/pages/AchievementsPage.tsx', 'frontend/src/pages/AchievementsPage.tsx'),
    ('agent-aceb5196/frontend/src/pages/AchievementsPage.css', 'frontend/src/pages/AchievementsPage.css'),
    ('agent-a04b4dec/frontend/src/pages/NewsletterPage.tsx', 'frontend/src/pages/NewsletterPage.tsx'),
    ('agent-a04b4dec/frontend/src/pages/NewsletterPage.css', 'frontend/src/pages/NewsletterPage.css'),
    ('agent-a59b1068/frontend/src/pages/MeetingSchedulerPage.tsx', 'frontend/src/pages/MeetingSchedulerPage.tsx'),
    ('agent-a59b1068/frontend/src/pages/MeetingSchedulerPage.css', 'frontend/src/pages/MeetingSchedulerPage.css'),
    ('agent-af1ba60b/frontend/src/pages/LessonSummarizerPage.tsx', 'frontend/src/pages/LessonSummarizerPage.tsx'),
    ('agent-af1ba60b/frontend/src/pages/LessonSummarizerPage.css', 'frontend/src/pages/LessonSummarizerPage.css'),
    ('agent-a8217a7b/frontend/src/pages/LearningJournalPage.tsx', 'frontend/src/pages/LearningJournalPage.tsx'),
    ('agent-a8217a7b/frontend/src/pages/LearningJournalPage.css', 'frontend/src/pages/LearningJournalPage.css'),
]

for src_rel, dst_rel in copies:
    src = os.path.join(BASE, src_rel)
    dst = os.path.join(MAIN, dst_rel)
    if os.path.exists(src):
        shutil.copy2(src, dst)
        print('OK: ' + dst_rel)
    else:
        print('MISSING SOURCE: ' + src)
