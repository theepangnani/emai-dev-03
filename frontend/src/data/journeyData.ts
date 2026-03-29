export interface JourneyStep {
  title: string;
  detail: string;
  tip?: string;
}

export interface Journey {
  id: string;
  title: string;
  description: string;
  steps: JourneyStep[];
  diagramUrl: string;
}

export interface JourneySection {
  role: string;
  journeys: Journey[];
}

export const JOURNEY_SECTIONS: JourneySection[] = [
  {
    role: 'Parent',
    journeys: [
      {
        id: 'p01',
        title: 'Registration & First Login',
        description: 'Create your ClassBridge account and complete onboarding as a parent.',
        steps: [
          { title: 'Visit ClassBridge', detail: 'Go to classbridge.ca and click the "Register" button on the landing page.' },
          { title: 'Fill Registration Form', detail: 'Enter your full name, email address, and choose a secure password.', tip: 'Use a password with at least 8 characters including letters and numbers.' },
          { title: 'Verify Your Email', detail: 'Check your inbox for a verification email from ClassBridge and click the confirmation link.' },
          { title: 'Select Parent Role', detail: 'On the onboarding screen, select "Parent" as your role to get the parent-focused experience.' },
          { title: 'Land on Dashboard', detail: 'You are now on your Parent Dashboard with quick actions, calendar, and child management tools.' },
        ],
        diagramUrl: '/help/journeys/p01.svg',
      },
      {
        id: 'p02',
        title: 'Add or Link Your Child',
        description: 'Add your child to ClassBridge so you can manage their courses and study materials.',
        steps: [
          { title: 'Go to My Kids', detail: 'Navigate to the "My Kids" page from the sidebar menu.' },
          { title: 'Click Add Child', detail: 'Click the "Add Child" button to open the child registration form.' },
          { title: 'Enter Child Details', detail: 'Enter your child\'s name. Email is optional — if provided, they will receive an invite to set their own password.', tip: 'You can add multiple children and switch between them on the dashboard.' },
          { title: 'Child Appears in List', detail: 'Your child now appears in your children list with their profile and course information.' },
          { title: 'Assign Courses', detail: 'Assign existing courses to your child or create new ones for them to start studying.' },
        ],
        diagramUrl: '/help/journeys/p02.svg',
      },
      {
        id: 'p03',
        title: 'Upload Course Material',
        description: 'Upload documents to a course so AI study tools become available.',
        steps: [
          { title: 'Navigate to Courses', detail: 'Go to the Courses page from the sidebar or dashboard quick actions.' },
          { title: 'Select or Create Course', detail: 'Choose an existing course or create a new one by clicking "+ Create Course".' },
          { title: 'Click Upload', detail: 'Click the "Upload" button within the course to open the file upload dialog.' },
          { title: 'Select Files', detail: 'Choose PDF, Word, or image files from your device. You can select multiple files at once.', tip: 'During upload, you can select which AI tools to auto-generate: Study Guide, Quiz, Flashcards.' },
          { title: 'Material Processes', detail: 'ClassBridge processes the document via OCR and text extraction. AI study tools become available once processing completes.' },
        ],
        diagramUrl: '/help/journeys/p03.svg',
      },
      {
        id: 'p04',
        title: 'Report Card Upload & AI Analysis',
        description: 'Upload a report card and get AI-powered grade analysis and career path suggestions.',
        steps: [
          { title: 'Go to My Kids', detail: 'Navigate to the "My Kids" page from the sidebar.' },
          { title: 'Select Your Child', detail: 'Click on the child whose report card you want to upload.' },
          { title: 'Click Upload Report Card', detail: 'Find the "Upload Report Card" button in your child\'s profile section.' },
          { title: 'Upload Image or PDF', detail: 'Upload a photo or PDF scan of the report card. ClassBridge uses OCR to extract the grades.', tip: 'For best results, ensure the report card image is clear and well-lit.' },
          { title: 'View AI Analysis', detail: 'AI extracts grades and provides a detailed analysis including strengths, areas for improvement, and career path suggestions based on academic performance.' },
        ],
        diagramUrl: '/help/journeys/p04.svg',
      },
      {
        id: 'p05',
        title: 'Understanding Your Dashboard',
        description: 'Learn the key areas of the parent dashboard and how to navigate them.',
        steps: [
          { title: 'Calendar View', detail: 'The calendar displays all tasks, assignments, and due dates for your children. Click any event for details.' },
          { title: 'Child Filter Tabs', detail: 'Use the child filter pills at the top to switch between children and see their individual data.' },
          { title: 'Quick Actions Bar', detail: 'The quick action cards let you upload materials, create courses, add children, and access AI tools with one click.' },
          { title: 'Study Guide Shortcuts', detail: 'Recent study materials appear on the dashboard for quick access to study guides, quizzes, and flashcards.' },
          { title: 'Activity Feed', detail: 'The activity feed shows recent actions across your children\'s accounts — uploads, quiz completions, and more.' },
        ],
        diagramUrl: '/help/journeys/p05.svg',
      },
      {
        id: 'p06',
        title: 'Messaging Your Child\'s Teacher',
        description: 'Send messages to teachers linked to your children.',
        steps: [
          { title: 'Go to My Kids', detail: 'Navigate to "My Kids" from the sidebar to see your children and their linked teachers.' },
          { title: 'Find Linked Teacher', detail: 'Locate the teacher linked to your child\'s course in the teachers section.' },
          { title: 'Click Message', detail: 'Click the "Message" button next to the teacher\'s name to open the compose window.' },
          { title: 'Compose and Send', detail: 'Write your message and click Send. You can include details about your child\'s progress or questions about assignments.' },
          { title: 'Teacher Gets Notification', detail: 'The teacher receives an email notification about your message and can reply directly from ClassBridge.', tip: 'You can also start messages from the Messages page in the sidebar.' },
        ],
        diagramUrl: '/help/journeys/p06.svg',
      },
      {
        id: 'p07',
        title: 'Creating Tasks & Reminders',
        description: 'Create and manage tasks for yourself or your children.',
        steps: [
          { title: 'Go to Tasks', detail: 'Navigate to the Tasks page from the sidebar menu.' },
          { title: 'Click Create Task', detail: 'Click the "+ Create Task" button to open the task creation form.' },
          { title: 'Set Details', detail: 'Enter a title, due date, and priority level for the task.' },
          { title: 'Assign to Child', detail: 'Optionally assign the task to one of your children so it appears on their dashboard too.', tip: 'Tasks appear on the calendar and you will get reminders before due dates.' },
          { title: 'Task on Calendar', detail: 'The task now appears on your calendar view. Click it to edit, reschedule by dragging, or mark as complete.' },
        ],
        diagramUrl: '/help/journeys/p07.svg',
      },
      {
        id: 'p08',
        title: 'Smart Daily Briefing & Help My Kid',
        description: 'Get a daily digest and coaching tips for your child\'s study materials.',
        steps: [
          { title: 'Daily Email Digest', detail: 'Each morning you receive an email summary of your child\'s upcoming tasks, overdue items, and recent activity.' },
          { title: 'Child Summary', detail: 'The briefing includes a per-child breakdown showing their study progress and any attention-needed items.' },
          { title: 'Help My Kid Button', detail: 'On course materials, click "Help My Kid" to get a plain-language summary designed for parents.', tip: 'Help My Kid uses 1 AI credit per request.' },
          { title: 'Coaching Tips', detail: 'The AI provides coaching tips explaining how to help your child understand the material without giving away answers.' },
        ],
        diagramUrl: '/help/journeys/p08.svg',
      },
      {
        id: 'p09',
        title: 'Managing Courses',
        description: 'Create, edit, and manage courses for your children.',
        steps: [
          { title: 'Courses Page', detail: 'Navigate to the Courses page to see all courses. You have full create, read, update, and delete capabilities.' },
          { title: 'Create a Course', detail: 'Click "+ Create Course" and enter the course name, subject, and description.' },
          { title: 'Assign to Children', detail: 'Assign courses to your children so they can access materials and AI study tools.' },
          { title: 'View Enrolled Students', detail: 'See which students are enrolled in each course and their progress.' },
          { title: 'Import from Google', detail: 'Optionally create courses by importing them from Google Classroom with a single click.', tip: 'Courses imported from Google Classroom sync assignments and grades automatically.' },
        ],
        diagramUrl: '/help/journeys/p09.svg',
      },
      {
        id: 'p10',
        title: 'Connecting Google Classroom',
        description: 'Link your Google account to auto-sync courses, assignments, and teachers.',
        steps: [
          { title: 'Go to Settings or Courses', detail: 'Navigate to Settings or the Courses page where the Google Classroom connection option is available.' },
          { title: 'Click Connect Google', detail: 'Click the "Connect Google Classroom" button to begin the authorization flow.' },
          { title: 'Authorize OAuth', detail: 'Sign in with your Google account and grant ClassBridge permission to access your Classroom data.', tip: 'Google Classroom connection is optional. You can always create courses manually.' },
          { title: 'Courses Auto-Sync', detail: 'Your Google Classroom courses, assignments, and linked teachers sync automatically to ClassBridge.' },
        ],
        diagramUrl: '/help/journeys/p10.svg',
      },
    ],
  },
  {
    role: 'Student',
    journeys: [
      {
        id: 's01',
        title: 'Registration & First Login',
        description: 'Create your account or accept an invite to start using ClassBridge as a student.',
        steps: [
          { title: 'Register or Accept Invite', detail: 'Visit classbridge.ca and register, or click the invite link from your parent or teacher.' },
          { title: 'Verify Email', detail: 'Check your inbox for a verification email and click the confirmation link.' },
          { title: 'Select Student Role', detail: 'On the onboarding screen, choose "Student" as your role.' },
          { title: 'Land on Dashboard', detail: 'You are now on your Student Dashboard with urgency pills, quick actions, and your upcoming timeline.' },
        ],
        diagramUrl: '/help/journeys/s01.svg',
      },
      {
        id: 's02',
        title: 'Generating a Study Guide',
        description: 'Use AI to create a formatted study guide from your course material.',
        steps: [
          { title: 'Open Course Material', detail: 'Navigate to a course and open the material you want to study.' },
          { title: 'Click Generate Study Guide', detail: 'Click the "Generate Study Guide" button on the material page.' },
          { title: 'AI Creates Guide', detail: 'The AI processes the material and creates a formatted study guide with sections, key points, and summaries.', tip: 'You can provide a focus prompt to target specific topics (e.g., "Focus on Chapter 5").' },
          { title: 'Streaming Generation', detail: 'The study guide appears in real-time as it is generated, so you can start reading immediately.' },
        ],
        diagramUrl: '/help/journeys/s02.svg',
      },
      {
        id: 's03',
        title: 'Taking a Practice Quiz',
        description: 'Generate and take AI-powered quizzes to test your knowledge.',
        steps: [
          { title: 'Open Material or Study Guide', detail: 'Go to a course material or study guide you want to be quizzed on.' },
          { title: 'Click Generate Quiz', detail: 'Click "Generate Quiz" to create a multiple-choice quiz from the content.' },
          { title: 'Take the Quiz', detail: 'Answer questions one by one with instant feedback on each answer.', tip: 'Your quiz results are saved automatically. Check Quiz History to track improvement.' },
          { title: 'Review Your Score', detail: 'After completing the quiz, review your total score and see which questions you got right or wrong.' },
        ],
        diagramUrl: '/help/journeys/s03.svg',
      },
      {
        id: 's04',
        title: 'Flashcards & Mind Maps',
        description: 'Generate flashcards and visual mind maps from your materials.',
        steps: [
          { title: 'Open Course Material', detail: 'Navigate to the course material you want to create flashcards or mind maps from.' },
          { title: 'Generate Flashcards', detail: 'Click "Generate Flashcards" to create front/back pairs covering key concepts.' },
          { title: 'Study with Flashcards', detail: 'Flip cards to test yourself. Mark each as "Known" or "Review Again" to track your progress.', tip: 'Use arrow keys or swipe to navigate between flashcards.' },
          { title: 'Generate Mind Map', detail: 'Click "Generate Mind Map" to create a visual diagram showing topic connections and relationships.' },
        ],
        diagramUrl: '/help/journeys/s04.svg',
      },
      {
        id: 's05',
        title: 'Study Q&A Chatbot',
        description: 'Ask the AI questions about your study material and get grounded answers.',
        steps: [
          { title: 'Open Any Material', detail: 'Navigate to a course material, study guide, or flashcard set.' },
          { title: 'Open Chatbot', detail: 'Click the "Ask a Question" or chat button to open the Q&A chatbot.' },
          { title: 'Ask Your Question', detail: 'Type a question about the material. The AI answers based on the specific content, not generic knowledge.', tip: 'Each question uses 1 AI credit from your wallet.' },
          { title: 'Get Cited Answers', detail: 'The AI provides answers grounded in your material with references to specific sections.' },
        ],
        diagramUrl: '/help/journeys/s05.svg',
      },
      {
        id: 's06',
        title: 'Notes & Text Highlights',
        description: 'Highlight text and add notes while studying.',
        steps: [
          { title: 'Open a Study Guide', detail: 'Navigate to any study guide or course material.' },
          { title: 'Highlight Text', detail: 'Select text in the study guide to highlight it. Choose a highlight color.' },
          { title: 'Add Notes', detail: 'Click the notes button to add personal notes. Notes are saved per material with revision history.', tip: 'You can create tasks directly from notes using the "Create Task" button in the notes panel.' },
          { title: 'Review Later', detail: 'Your highlights and notes persist across sessions so you can review them anytime.' },
        ],
        diagramUrl: '/help/journeys/s06.svg',
      },
      {
        id: 's07',
        title: 'Tasks, XP Points & Study Streaks',
        description: 'Manage tasks, earn XP for study actions, and maintain your study streak.',
        steps: [
          { title: 'Tasks Page', detail: 'Go to the Tasks page to see all tasks organized by Overdue, Today, This Week, and Later.' },
          { title: 'Earn XP Points', detail: 'Earn Experience Points for study activities: quizzes, flashcards, study guides, and completing tasks.' },
          { title: 'Maintain Study Streak', detail: 'Complete at least one study action each day to keep your streak going. Your streak count is shown on the dashboard.', tip: 'School holidays set by admins will not break your streak.' },
          { title: 'Freeze Tokens', detail: 'If you miss a day, you can spend XP to recover your streak before it resets.' },
        ],
        diagramUrl: '/help/journeys/s07.svg',
      },
      {
        id: 's08',
        title: 'Study With Me Pomodoro Timer',
        description: 'Use the built-in Pomodoro timer for focused study sessions.',
        steps: [
          { title: 'Open Timer', detail: 'Find the "Study With Me" timer on your dashboard or from the sidebar.' },
          { title: 'Start a Session', detail: 'Click Start to begin a 25-minute focused study session.' },
          { title: 'Take Breaks', detail: 'After 25 minutes, take a 5-minute break. The timer manages the cycle automatically.', tip: 'Study sessions are tracked and contribute to your XP and study streak.' },
          { title: 'Track Sessions', detail: 'Your Pomodoro sessions are logged so you can see how much focused study time you have accumulated.' },
        ],
        diagramUrl: '/help/journeys/s08.svg',
      },
      {
        id: 's09',
        title: 'Student Dashboard Overview',
        description: 'Understand the key elements of your student dashboard.',
        steps: [
          { title: 'Hero Greeting', detail: 'The top of the dashboard shows a personalized greeting with urgency pills for overdue and due-today items.' },
          { title: 'Quick Action Cards', detail: 'Quick action cards let you upload materials, create courses, or start studying with a single click.' },
          { title: 'Coming Up Timeline', detail: 'The "Coming Up" section shows your upcoming assignments and tasks in chronological order.' },
          { title: 'Recent Materials', detail: 'Recently accessed study materials appear for quick re-entry into your study sessions.' },
          { title: 'Course Chips', detail: 'Course chips at the top let you filter the dashboard view by individual courses.' },
        ],
        diagramUrl: '/help/journeys/s09.svg',
      },
      {
        id: 's10',
        title: 'Assessment Countdown & Study History',
        description: 'Track upcoming tests and review your personal study history.',
        steps: [
          { title: 'Countdown Widgets', detail: 'Upcoming tests display countdown widgets color-coded by urgency: red for imminent, yellow for approaching, green for distant.' },
          { title: 'Test Details', detail: 'Click any countdown widget to see test details, related materials, and study resources.' },
          { title: 'Study History Timeline', detail: 'View your personal study history showing daily session logs, materials reviewed, and time spent.', tip: 'Use your study history to identify patterns and optimize your study schedule.' },
          { title: 'Daily Session Logs', detail: 'Each day shows a breakdown of study activities: quizzes taken, flashcards reviewed, guides created, and time totals.' },
        ],
        diagramUrl: '/help/journeys/s10.svg',
      },
    ],
  },
  {
    role: 'Teacher',
    journeys: [
      {
        id: 't01',
        title: 'Registration & Setup',
        description: 'Create your teacher account and set up your profile.',
        steps: [
          { title: 'Register on ClassBridge', detail: 'Visit classbridge.ca and click Register. Fill in your name, email, and password.' },
          { title: 'Select Teacher Role', detail: 'On the onboarding screen, select "Teacher" as your role.' },
          { title: 'Choose Teacher Type', detail: 'Select whether you are a school teacher or a private tutor. This affects available features.', tip: 'You can update your teacher type later in Settings.' },
          { title: 'Set Up Profile', detail: 'Complete your profile with school name, subjects taught, and a brief bio.' },
        ],
        diagramUrl: '/help/journeys/t01.svg',
      },
      {
        id: 't02',
        title: 'Create a Class & Manage Roster',
        description: 'Set up a class and add students to your roster.',
        steps: [
          { title: 'Click Create Class', detail: 'From your dashboard or Classes page, click "+ Create Class" to start.' },
          { title: 'Enter Class Details', detail: 'Fill in the class name, subject, and grade level.' },
          { title: 'Add Students', detail: 'Add students by email address or share the class code for self-enrollment.', tip: 'Students who are not on ClassBridge yet will receive an invite email.' },
          { title: 'Manage Enrollment', detail: 'View your roster, remove students, or approve pending join requests from the class settings.' },
        ],
        diagramUrl: '/help/journeys/t02.svg',
      },
      {
        id: 't03',
        title: 'Upload Materials & Create Assignments',
        description: 'Share course materials and create assignments for your students.',
        steps: [
          { title: 'Upload Materials', detail: 'Go to your course and click "Upload Material." Select PDF, Word, or image files.' },
          { title: 'Materials Process', detail: 'ClassBridge processes the files so AI study tools become available to students.', tip: 'You can select which AI tools to auto-generate during upload.' },
          { title: 'Create Assignment', detail: 'Click "Create Assignment" and set a title, description, due date, and max points.' },
          { title: 'Students Get Tools', detail: 'Enrolled students are notified and can generate study guides, quizzes, and flashcards from your materials.' },
        ],
        diagramUrl: '/help/journeys/t03.svg',
      },
      {
        id: 't04',
        title: 'Syncing Google Classroom',
        description: 'Connect Google Classroom to automatically sync courses and rosters.',
        steps: [
          { title: 'Connect Google Account', detail: 'Click "Connect Google Classroom" from your dashboard or Settings page.' },
          { title: 'Authorize Access', detail: 'Sign in with your Google account and grant ClassBridge permission to access Classroom data.' },
          { title: 'Select Courses to Sync', detail: 'Choose which Google Classroom courses to import into ClassBridge.', tip: 'You can connect multiple Google accounts (personal and school) to sync from different sources.' },
          { title: 'Auto-Sync Active', detail: 'Assignments, roster changes, and grades sync automatically going forward.' },
        ],
        diagramUrl: '/help/journeys/t04.svg',
      },
      {
        id: 't05',
        title: 'Communicating with Parents & Students',
        description: 'Send messages to parents and students enrolled in your courses.',
        steps: [
          { title: 'Go to Messages', detail: 'Navigate to the Messages page from the sidebar.' },
          { title: 'Compose Message', detail: 'Click "New Message" and select recipients from enrolled parents or students.' },
          { title: 'Send Message', detail: 'Write your message and send. Recipients get email notifications.', tip: 'Message history is preserved so you can reference past conversations.' },
          { title: 'Check Replies', detail: 'View replies in your message inbox. Unread messages are highlighted.' },
        ],
        diagramUrl: '/help/journeys/t05.svg',
      },
      {
        id: 't06',
        title: 'Teacher Dashboard Overview',
        description: 'Understand the key areas of your teacher dashboard.',
        steps: [
          { title: 'Class Overview', detail: 'See all your classes at a glance with student counts and recent activity.' },
          { title: 'Student Progress', detail: 'View aggregated student engagement metrics including quiz scores and study time.' },
          { title: 'Assignment Status', detail: 'Track assignment submission rates and upcoming due dates across all classes.' },
          { title: 'Recent Activity', detail: 'The activity feed shows recent student actions: material views, quiz completions, and submissions.' },
        ],
        diagramUrl: '/help/journeys/t06.svg',
      },
      {
        id: 't07',
        title: 'Inviting Parents & Students',
        description: 'Send email invites for parents or students to join your course.',
        steps: [
          { title: 'Open Invite Flow', detail: 'From your class or dashboard, click "Invite Parent" or "Invite Student."' },
          { title: 'Enter Email', detail: 'Enter the email address of the person you want to invite.' },
          { title: 'Send Invite', detail: 'Click Send. The recipient gets an email with a link to join ClassBridge and your course.', tip: 'Parents who accept the invite are automatically linked to their child in your course.' },
          { title: 'Track Acceptance', detail: 'See pending and accepted invites in your class roster.' },
        ],
        diagramUrl: '/help/journeys/t07.svg',
      },
      {
        id: 't08',
        title: 'Viewing Student Progress',
        description: 'Monitor individual student performance and engagement.',
        steps: [
          { title: 'Select a Student', detail: 'From your class roster, click on a student to view their individual progress.' },
          { title: 'Quiz Scores', detail: 'See per-student quiz scores across all materials in your course.' },
          { title: 'Study Activity', detail: 'View study guide generation activity, flashcard usage, and time spent studying.' },
          { title: 'Engagement Metrics', detail: 'Review overall engagement metrics including login frequency, materials accessed, and completion rates.', tip: 'Use these insights to identify students who may need additional support.' },
        ],
        diagramUrl: '/help/journeys/t08.svg',
      },
    ],
  },
  {
    role: 'Admin',
    journeys: [
      {
        id: 'a01',
        title: 'Admin Dashboard Overview',
        description: 'Understand the platform health metrics and administrative tools.',
        steps: [
          { title: 'Platform Health Metrics', detail: 'The dashboard displays key metrics: total users, active users, AI usage, and system health indicators.' },
          { title: 'User Stats', detail: 'View user registration trends, role distribution, and growth metrics.' },
          { title: 'AI Usage Overview', detail: 'Monitor platform-wide AI credit consumption and usage patterns.' },
          { title: 'Activity Feed', detail: 'The recent activity feed shows platform events: registrations, logins, content creation, and administrative actions.' },
          { title: 'Clickable Metrics', detail: 'Click any metric card to drill down into detailed views and management pages.' },
        ],
        diagramUrl: '/help/journeys/a01.svg',
      },
      {
        id: 'a02',
        title: 'Managing Users',
        description: 'Search, filter, and manage user accounts across the platform.',
        steps: [
          { title: 'User List', detail: 'Navigate to the Users page to see all registered users with search and filter capabilities.' },
          { title: 'Search and Filter', detail: 'Search by name or email, filter by role (Parent, Student, Teacher, Admin), or account status.' },
          { title: 'Role Management', detail: 'Click a user to view their profile and manage their role assignments.' },
          { title: 'Account Actions', detail: 'Activate, deactivate, or reset passwords for user accounts.', tip: 'Deactivated accounts enter a grace period before data is anonymized.' },
        ],
        diagramUrl: '/help/journeys/a02.svg',
      },
      {
        id: 'a03',
        title: 'Broadcast & Individual Messages',
        description: 'Send platform-wide broadcasts or targeted messages to individual users.',
        steps: [
          { title: 'Send Broadcast', detail: 'Click "Send Broadcast" to compose a message that goes to all platform users via in-app notification and email.' },
          { title: 'Individual Messages', detail: 'Send targeted messages to specific users from the Messages page or user profile.' },
          { title: 'View History', detail: 'Review sent message history including delivery status and read receipts.', tip: 'You can reuse previous broadcast messages as templates for new ones.' },
        ],
        diagramUrl: '/help/journeys/a03.svg',
      },
      {
        id: 'a04',
        title: 'Managing AI Usage Limits',
        description: 'Configure and monitor AI credit quotas across the platform.',
        steps: [
          { title: 'AI Usage Page', detail: 'Navigate to the AI Usage page to see platform-wide credit consumption.' },
          { title: 'Set Default Limits', detail: 'Configure default AI interaction quotas that apply to new users.' },
          { title: 'Per-User Adjustments', detail: 'Adjust individual user limits from their profile page or the AI usage management table.' },
          { title: 'Monitor Usage', detail: 'Track credit consumption trends and identify heavy users.', tip: 'Review pending credit increase requests from users who have hit their limits.' },
        ],
        diagramUrl: '/help/journeys/a04.svg',
      },
      {
        id: 'a05',
        title: 'Audit Log & FAQ Management',
        description: 'Review platform audit logs and manage Help Center FAQ articles.',
        steps: [
          { title: 'Audit Log', detail: 'View all audit log entries showing logins, content changes, role modifications, and security events.' },
          { title: 'Filter Events', detail: 'Filter audit entries by date, user, event type, or severity.' },
          { title: 'FAQ Management', detail: 'Manage Help Center FAQ articles: create new articles, edit existing ones, and toggle draft/publish status.' },
          { title: 'Publish Articles', detail: 'Published articles appear in the Help Center search results for all users.', tip: 'Use draft status to prepare articles before making them visible to users.' },
        ],
        diagramUrl: '/help/journeys/a05.svg',
      },
    ],
  },
  {
    role: 'Cross-Role',
    journeys: [
      {
        id: 'x01',
        title: 'How Parents, Students & Teachers Work Together',
        description: 'See how the three roles connect through courses, materials, and messaging.',
        steps: [
          { title: 'Parent Uploads Material', detail: 'A parent uploads a PDF or document to a course assigned to their child.' },
          { title: 'Student Generates Study Guide', detail: 'The student opens the material and generates an AI study guide, quiz, or flashcards.' },
          { title: 'Teacher Sees Progress', detail: 'The teacher views the student\'s quiz scores, study activity, and engagement metrics from their dashboard.' },
          { title: 'Messaging Connects All Three', detail: 'Parents can message teachers, teachers can message parents and students, and everyone stays informed through the same platform.', tip: 'All three roles see the same course data from their own perspective.' },
        ],
        diagramUrl: '/help/journeys/x01.svg',
      },
      {
        id: 'x02',
        title: 'Using ClassBridge on Mobile',
        description: 'Access ClassBridge on your phone via responsive web or the mobile app.',
        steps: [
          { title: 'Responsive Web', detail: 'ClassBridge works in any mobile browser. Navigate to classbridge.ca and log in as usual — the interface adapts to your screen size.' },
          { title: 'Mobile App', detail: 'Download the ClassBridge mobile app (Expo-based) for an optimized mobile experience with key features.' },
          { title: 'Key Features on Mobile', detail: 'Access your dashboard, view courses, study materials, take quizzes, and send messages from your phone.', tip: 'The mobile app supports push notifications for new messages and assignment reminders.' },
        ],
        diagramUrl: '/help/journeys/x02.svg',
      },
    ],
  },
];

export const ALL_ROLES = JOURNEY_SECTIONS.map(s => s.role);
