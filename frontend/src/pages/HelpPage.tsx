import { useState, useMemo } from 'react';
import { useAuth } from '../context/AuthContext';
import { DashboardLayout } from '../components/DashboardLayout';
import { PageNav } from '../components/PageNav';
import './HelpPage.css';

/* ──────────────── Tutorial types & data ──────────────── */

interface TutorialStep {
  title: string;
  description: string;
  image: string;
  tip?: string;
}

interface TutorialSection {
  id: string;
  title: string;
  description: string;
  steps: TutorialStep[];
}

const PARENT_TUTORIALS: TutorialSection[] = [
  {
    id: 'parent-start',
    title: 'Getting Started as a Parent',
    description: 'Set up your account and add your children to ClassBridge.',
    steps: [
      {
        title: 'Add Your Child',
        description: 'From the dashboard, click the + button on the child pills row, then select "Add Child." Enter your child\'s name (email is optional). If you provide an email, they\'ll receive an invite to set their own password.',
        image: '/tutorial/parent-add-child.svg',
        tip: 'You can add multiple children and switch between them using the filter pills at the top of your dashboard.',
      },
      {
        title: 'Connect Google Classroom',
        description: 'Click "Connect Google Classroom" on your dashboard to link your Google account. This lets you import your child\'s courses, assignments, and grades automatically.',
        image: '/tutorial/parent-google-connect.svg',
        tip: 'Google Classroom connection is optional. You can create courses and upload materials manually without it.',
      },
      {
        title: 'View Your Child\'s Dashboard',
        description: 'Select a child from the filter pills to see their courses, upcoming tasks, and study materials. The "Today\'s Focus" header shows overdue items and due-today counts at a glance.',
        image: '/tutorial/parent-dashboard.svg',
      },
    ],
  },
  {
    id: 'parent-study',
    title: 'Creating Study Materials',
    description: 'Upload documents and generate AI-powered study tools for your child.',
    steps: [
      {
        title: 'Upload a Document',
        description: 'Click the + button and select "Upload Documents." You can upload PDFs, Word docs, or PowerPoint files. Select multiple files at once — each becomes a course material.',
        image: '/tutorial/parent-upload.svg',
        tip: 'During upload, you can select which AI tools to generate: Study Guide, Quiz, Flashcards, or all three.',
      },
      {
        title: 'Generate AI Study Tools',
        description: 'Open any course material and click "Generate" on the Study Guide, Quiz, or Flashcards tab. You can provide a focus prompt to guide the AI (e.g., "Focus on Chapter 5 vocabulary").',
        image: '/tutorial/parent-generate.svg',
        tip: 'Generation happens in the background — you can keep working while AI creates the materials.',
      },
      {
        title: 'Review & Print Materials',
        description: 'Each course material has tabs for the original document, study guide, quiz, and flashcards. Use the Print or Download PDF buttons to create offline study resources.',
        image: '/tutorial/parent-review.svg',
      },
    ],
  },
  {
    id: 'parent-communicate',
    title: 'Communication & Tasks',
    description: 'Message teachers and manage your child\'s tasks.',
    steps: [
      {
        title: 'Message a Teacher',
        description: 'Go to Messages in the sidebar. Click "New Message" and select a teacher from the recipients list. Teachers are available if your child is enrolled in their course or you\'ve linked them manually.',
        image: '/tutorial/parent-message.svg',
      },
      {
        title: 'Link a Teacher Manually',
        description: 'On the My Kids page, find your child and scroll to the Teachers section. Click "Add Teacher" and enter their email. They\'ll receive an invite if they\'re not on ClassBridge yet.',
        image: '/tutorial/parent-link-teacher.svg',
      },
      {
        title: 'Create & Track Tasks',
        description: 'Use the Tasks page to create tasks for yourself or assign them to your children. Tasks appear on the calendar and you\'ll get reminders before due dates.',
        image: '/tutorial/parent-tasks.svg',
        tip: 'Click any task in the calendar to see details, reschedule by dragging, or mark as complete.',
      },
    ],
  },
];

const STUDENT_TUTORIALS: TutorialSection[] = [
  {
    id: 'student-start',
    title: 'Getting Started as a Student',
    description: 'Set up your workspace and start organizing your studies.',
    steps: [
      {
        title: 'Explore Your Dashboard',
        description: 'Your dashboard shows urgency pills (overdue/due today), quick actions, and a "Coming Up" timeline with all your assignments and tasks. Use the quick action cards to upload materials or create courses.',
        image: '/tutorial/student-dashboard.svg',
      },
      {
        title: 'Create or Join a Course',
        description: 'Go to the Study Hub and click "+ Create Class" to add your own course. You can also browse and self-enroll in existing courses shared by teachers.',
        image: '/tutorial/student-courses.svg',
        tip: 'Courses help organize your materials by subject. Every uploaded document belongs to a course.',
      },
      {
        title: 'Upload Study Materials',
        description: 'Click "Upload Materials" from the dashboard or Study Hub. Drop in PDFs, Word docs, or images of handouts. Select which AI tools you want generated during upload.',
        image: '/tutorial/student-upload.svg',
      },
    ],
  },
  {
    id: 'student-study',
    title: 'Using AI Study Tools',
    description: 'Generate study guides, take quizzes, and practice with flashcards.',
    steps: [
      {
        title: 'Generate a Study Guide',
        description: 'Open any course material and click "Generate" on the Study Guide tab. Add a focus prompt to target specific topics. The AI creates a structured summary with key concepts.',
        image: '/tutorial/student-study-guide.svg',
        tip: 'For math content, the AI automatically provides step-by-step worked solutions.',
      },
      {
        title: 'Take a Practice Quiz',
        description: 'Switch to the Quiz tab and generate a quiz. Choose Easy, Medium, or Hard difficulty. Answer questions one by one with instant feedback, then review your score.',
        image: '/tutorial/student-quiz.svg',
        tip: 'Your quiz results are saved automatically. Check Quiz History to track your improvement over time.',
      },
      {
        title: 'Study with Flashcards',
        description: 'The Flashcards tab generates flip cards from your material. Click to flip, use arrow keys or swipe to navigate, and shuffle for variety.',
        image: '/tutorial/student-flashcards.svg',
      },
    ],
  },
  {
    id: 'student-organize',
    title: 'Staying Organized',
    description: 'Use tasks, notes, and the calendar to stay on top of your work.',
    steps: [
      {
        title: 'Manage Your Tasks',
        description: 'The Tasks page shows all your assignments and personal tasks grouped by urgency: Overdue, Due Today, This Week, and Later. Create new tasks with the + button.',
        image: '/tutorial/student-tasks.svg',
      },
      {
        title: 'Take Notes While Studying',
        description: 'Click the Notes button (bottom-right) while viewing any study material. Your notes auto-save and are tied to that specific material. Highlight text to add it as a quote.',
        image: '/tutorial/student-notes.svg',
        tip: 'You can create tasks directly from your notes using the "Create Task" button in the notes panel.',
      },
      {
        title: 'Use the Calendar',
        description: 'The calendar on the Tasks page shows all your assignments and tasks. Drag tasks to reschedule them. Switch between Month, Week, 3-Day, and Day views.',
        image: '/tutorial/student-calendar.svg',
      },
    ],
  },
];

const TEACHER_TUTORIALS: TutorialSection[] = [
  {
    id: 'teacher-start',
    title: 'Getting Started as a Teacher',
    description: 'Set up your courses and manage your classroom.',
    steps: [
      {
        title: 'Create a Course',
        description: 'From your dashboard, click "Create Course" or go to Classes in the sidebar. Enter a course name, subject, and description. You can also connect Google Classroom to import existing courses.',
        image: '/tutorial/teacher-create-course.svg',
        tip: 'You can connect multiple Google accounts (personal + school) to sync courses from different sources.',
      },
      {
        title: 'Add Students to Your Course',
        description: 'Open a course and scroll to the Student Roster section. Click "Add Student" and enter their email. If they\'re not on ClassBridge yet, they\'ll receive an invite.',
        image: '/tutorial/teacher-add-students.svg',
      },
      {
        title: 'Create Assignments',
        description: 'On the course detail page, find the Assignments section and click "Create Assignment." Set a title, description, due date, and max points. Enrolled students are notified automatically.',
        image: '/tutorial/teacher-assignments.svg',
      },
    ],
  },
  {
    id: 'teacher-materials',
    title: 'Sharing Course Materials',
    description: 'Upload and share study materials with your students.',
    steps: [
      {
        title: 'Upload Course Materials',
        description: 'Go to Course Materials in the sidebar or use the "Upload Material" quick action. Select your course, upload files, and optionally generate AI study tools during upload.',
        image: '/tutorial/teacher-upload.svg',
      },
      {
        title: 'Invite Parents',
        description: 'From your dashboard, use the "Invite Parent" card. Enter the parent\'s email and select the student. The parent will receive an invitation to join ClassBridge and will automatically be linked to their child.',
        image: '/tutorial/teacher-invite-parent.svg',
      },
      {
        title: 'Communicate with Parents',
        description: 'Go to Messages to communicate with parents of your enrolled students. You can also check Teacher Communications to see synced emails and announcements with AI summaries.',
        image: '/tutorial/teacher-messages.svg',
      },
    ],
  },
];

const ADMIN_TUTORIALS: TutorialSection[] = [
  {
    id: 'admin-start',
    title: 'Platform Administration',
    description: 'Manage users, monitor platform activity, and send communications.',
    steps: [
      {
        title: 'User Management',
        description: 'Your dashboard shows platform statistics and a user management table. Search, filter by role, and click any user to view their details. You can manage roles, send messages, or adjust settings per user.',
        image: '/tutorial/admin-users.svg',
      },
      {
        title: 'Manage the Waitlist',
        description: 'Go to Waitlist in the sidebar to view pending signups. Approve users to send them a registration invite, or decline with a polite message. Use the stats bar to track conversion rates.',
        image: '/tutorial/admin-waitlist.svg',
      },
      {
        title: 'Monitor AI Usage',
        description: 'The AI Usage page shows credit consumption across all users. Review pending credit requests, adjust individual limits, or reset usage counts. The overview tab shows top users and trends.',
        image: '/tutorial/admin-ai-usage.svg',
      },
    ],
  },
  {
    id: 'admin-communicate',
    title: 'Communications & Monitoring',
    description: 'Broadcast messages and monitor platform health.',
    steps: [
      {
        title: 'Send a Broadcast',
        description: 'Click "Send Broadcast" on your dashboard to compose a message that goes to all platform users via in-app notification and email. Use this for announcements, updates, or maintenance notices.',
        image: '/tutorial/admin-broadcast.svg',
      },
      {
        title: 'Manage Inspirational Messages',
        description: 'Go to the Inspiration page to manage role-specific motivational quotes shown on dashboards and in emails. Add, edit, or toggle messages per role (Parent, Student, Teacher).',
        image: '/tutorial/admin-inspiration.svg',
      },
      {
        title: 'View Audit Logs',
        description: 'The Audit Log page shows a chronological record of all platform events: logins, registrations, content changes, and security events. Use it to investigate issues or verify compliance.',
        image: '/tutorial/admin-audit.svg',
      },
    ],
  },
];

/* ──────────────── FAQ types & data ──────────────── */

interface FaqItem {
  question: string;
  answer: string;
}

interface FaqSection {
  title: string;
  items: FaqItem[];
}

const FAQ_SECTIONS: FaqSection[] = [
  {
    title: 'Getting Started',
    items: [
      {
        question: 'How do I connect my Google Classroom account?',
        answer:
          'Go to your Dashboard and click the "Connect Google Classroom" button. You\'ll be redirected to Google to sign in and grant ClassBridge permission to access your Classroom data. Once connected, your classes and assignments will sync automatically.',
      },
      {
        question: 'How do I sync my classes and assignments?',
        answer:
          'After connecting Google Classroom, your classes sync automatically. To manually refresh, click the sync button on your Dashboard or Classes page. Assignments, due dates, and class materials will be pulled from Google Classroom.',
      },
      {
        question: 'How do I link my child\'s account (for parents)?',
        answer:
          'From your Dashboard, go to "Child Profiles" and click "Invite Child." Enter your child\'s email address to send them an invitation. Once they accept and create their account, you\'ll be able to view their classes, assignments, and progress.',
      },
    ],
  },
  {
    title: 'Study Tools',
    items: [
      {
        question: 'How do I create a study guide from class materials?',
        answer:
          'Navigate to "Class Materials," select a class, and click "Generate Study Guide." ClassBridge uses AI to create a structured study guide from your class content. You can also upload your own files (PDFs, documents) to generate guides from.',
      },
      {
        question: 'How do I take a quiz or use flashcards?',
        answer:
          'Open any study guide and click "Take Quiz" or "Flashcards" to generate interactive study tools from that guide\'s content. Quizzes provide multiple-choice questions with instant feedback, and flashcards let you review key concepts.',
      },
      {
        question: 'How do I upload files for study guide generation?',
        answer:
          'On the "Class Materials" page, click "Upload Material." You can upload PDFs, Word documents, and other text files. ClassBridge will process the content and let you generate AI-powered study guides, quizzes, and flashcards from them.',
      },
    ],
  },
  {
    title: 'Communication',
    items: [
      {
        question: 'How do I send a message to a teacher or parent?',
        answer:
          'Go to "Messages" in the sidebar. Click "New Message" to start a conversation. Select the recipient from the list of connected teachers or parents, type your message, and send. You\'ll receive notifications when they reply.',
      },
      {
        question: 'How do I manage my notification preferences?',
        answer:
          'Click the bell icon in the top-right corner to view your notifications. You can mark notifications as read or dismiss them. Email notifications for important events like new messages and assignment reminders are sent automatically.',
      },
    ],
  },
  {
    title: 'Account & Settings',
    items: [
      {
        question: 'How do I create and track tasks?',
        answer:
          'Go to "Tasks" in the sidebar. Click "New Task" to create a personal task with a title, description, and optional due date. Tasks can be marked as complete as you finish them, helping you stay organized alongside your assignments.',
      },
      {
        question: 'How do I switch between roles (multi-role users)?',
        answer:
          'If you have multiple roles (e.g., both teacher and parent), click on your role badge next to your name in the top-right corner. A dropdown will appear letting you switch between your available roles. Your view will update accordingly.',
      },
      {
        question: 'How do I disconnect or reconnect Google Classroom?',
        answer:
          'To disconnect Google Classroom, go to your Dashboard and look for the Google Classroom connection section. Click "Disconnect" to remove the link. You can reconnect at any time by clicking "Connect Google Classroom" again.',
      },
      {
        question: 'How do I view my child\'s classes and assignments?',
        answer:
          'As a parent, go to "Child Profiles" and select your child. You\'ll see their linked classes, upcoming assignments, and any study materials they\'ve created. This gives you visibility into their academic progress.',
      },
      {
        question: 'How do I change my password or update my profile?',
        answer:
          'Currently, you can reset your password using the "Forgot Password" link on the login page, which sends a reset link to your email. Profile updates including name changes can be managed from your account settings.',
      },
    ],
  },
  {
    title: 'Troubleshooting',
    items: [
      {
        question: 'What should I do if my Google sync fails?',
        answer:
          'First, try clicking the sync button again. If it still fails, your Google authorization may have expired \u2014 go to your Dashboard and reconnect Google Classroom. If the problem persists, sign out and sign back in, then reconnect.',
      },
      {
        question: 'Where can I report a bug or request a feature?',
        answer:
          'Please email us at support@classbridge.ca with a description of the issue or your feature idea. Include screenshots if possible. We review all feedback and use it to improve ClassBridge.',
      },
    ],
  },
  {
    title: 'Why ClassBridge? (vs ChatGPT / Claude)',
    items: [
      {
        question:
          'How is ClassBridge different from using ChatGPT or Claude?',
        answer:
          "General AI tools are generic, stateless, and prompt-driven. ClassBridge is an integrated platform that connects real school data with AI capabilities, wrapped in role-appropriate views for each stakeholder. The parent doesn't need to be an AI prompt engineer — they open the app and see their child's assignments, grades, and AI-generated study materials automatically. The value isn't the AI itself — it's the data integration, workflow automation, and multi-stakeholder coordination that makes the AI actually useful in a school context without any effort from the user.",
      },
      {
        question:
          "What does Google Classroom integration give me that ChatGPT can't?",
        answer:
          "ClassBridge auto-syncs courses, assignments, and grades directly from Google Classroom. Parents see their child's actual schoolwork without asking the kid or logging into their account. General AI tools have zero access to a student's real classroom data.",
      },
      {
        question: 'How does the role-based family/school ecosystem work?',
        answer:
          "Parents, students, teachers, and admins each get a tailored experience. Parents can monitor multiple children, see their grades, and get AI-generated insights on actual performance. Teachers get communication tools and announcement monitoring. ChatGPT doesn't know who your kid is or what class they're in.",
      },
      {
        question: 'What makes ClassBridge study tools context-aware?',
        answer:
          "Study guides, quizzes, and flashcards are generated from real assignments and course materials — not generic prompts. A parent or student doesn't need to copy-paste assignment details into a chatbot and craft the right prompt.",
      },
      {
        question:
          'How does ClassBridge handle parent-teacher communication?',
        answer:
          'ClassBridge has a built-in communication channel between parents and teachers, integrated with the same platform where grades and assignments live. It also includes Gmail/announcement monitoring for teacher communications.',
      },
      {
        question:
          'What automated notifications and reminders does ClassBridge provide?',
        answer:
          "ClassBridge sends assignment reminders at 8am and syncs teacher communications every 15 minutes. These are proactive alerts — no one has to remember to check. General AI tools don't track your schedule or send reminders.",
      },
      {
        question: "Does ClassBridge track my child's progress over time?",
        answer:
          "Yes. ClassBridge maintains a persistent student profile with grade tracking, analytics, and AI insights over time. ChatGPT starts fresh every conversation — it doesn't track your child's academic trajectory.",
      },
      {
        question:
          'Will ClassBridge integrate directly with school boards and teachers?',
        answer:
          "Currently, ClassBridge integrates with Google Classroom through the parent or student's own Google account. Direct integration with school boards and teacher-managed systems requires institutional permissions that are not yet in place. We are actively working on partnerships and approval processes to enable school-level and board-level integration in future phases. Stay tuned — this is a top priority on our roadmap.",
      },
    ],
  },
];

/* ──────────────── Component ──────────────── */

export function HelpPage() {
  const { user } = useAuth();
  const [expandedFaq, setExpandedFaq] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<string | null>(null);
  const [activeStep, setActiveStep] = useState(0);

  const tutorials = useMemo(() => {
    switch (user?.role) {
      case 'parent': return PARENT_TUTORIALS;
      case 'student': return STUDENT_TUTORIALS;
      case 'teacher': return TEACHER_TUTORIALS;
      case 'admin': return ADMIN_TUTORIALS;
      default: return PARENT_TUTORIALS;
    }
  }, [user?.role]);

  const roleName = user?.role
    ? user.role.charAt(0).toUpperCase() + user.role.slice(1)
    : 'User';

  const currentSection = tutorials.find(s => s.id === activeSection);

  const handleSectionClick = (sectionId: string) => {
    if (activeSection === sectionId) {
      setActiveSection(null);
      setActiveStep(0);
    } else {
      setActiveSection(sectionId);
      setActiveStep(0);
    }
  };

  const handleNext = () => {
    if (currentSection && activeStep < currentSection.steps.length - 1) {
      setActiveStep(prev => prev + 1);
    }
  };

  const handlePrev = () => {
    if (activeStep > 0) {
      setActiveStep(prev => prev - 1);
    }
  };

  const toggleFaq = (key: string) => {
    setExpandedFaq(prev => (prev === key ? null : key));
  };

  return (
    <DashboardLayout welcomeSubtitle="Find answers to common questions" showBackButton>
      <div className="help-container">
        <PageNav items={[
          { label: 'Home', to: '/dashboard' },
          { label: 'Help' },
        ]} />

        {/* ── Tutorial Section ── */}
        <div className="tut-header">
          <h2 className="tut-title">Welcome, {roleName}!</h2>
          <p className="tut-subtitle">
            Follow these interactive guides to get the most out of ClassBridge.
            Select a topic below to begin.
          </p>
        </div>

        <div className="tut-sections">
          {tutorials.map((section) => {
            const isActive = activeSection === section.id;
            return (
              <div key={section.id} className={`tut-section${isActive ? ' active' : ''}`}>
                <button
                  className="tut-section-header"
                  onClick={() => handleSectionClick(section.id)}
                  aria-expanded={isActive}
                >
                  <div className="tut-section-info">
                    <h3 className="tut-section-title">{section.title}</h3>
                    <p className="tut-section-desc">{section.description}</p>
                  </div>
                  <span className="tut-section-badge">{section.steps.length} steps</span>
                  <span className={`tut-chevron${isActive ? ' expanded' : ''}`}>&#9654;</span>
                </button>

                {isActive && currentSection && (
                  <div className="tut-step-viewer">
                    <div className="tut-progress">
                      {currentSection.steps.map((_, idx) => (
                        <button
                          key={idx}
                          className={`tut-dot${idx === activeStep ? ' active' : ''}${idx < activeStep ? ' completed' : ''}`}
                          onClick={() => setActiveStep(idx)}
                          aria-label={`Step ${idx + 1}`}
                        >
                          {idx < activeStep ? (
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                              <polyline points="20 6 9 17 4 12"/>
                            </svg>
                          ) : (
                            <span>{idx + 1}</span>
                          )}
                        </button>
                      ))}
                    </div>

                    <div className="tut-step">
                      <div className="tut-step-image-wrap">
                        <img
                          src={currentSection.steps[activeStep].image}
                          alt={currentSection.steps[activeStep].title}
                          className="tut-step-image"
                          onError={(e) => {
                            (e.target as HTMLImageElement).style.display = 'none';
                            const parent = (e.target as HTMLImageElement).parentElement;
                            if (parent && !parent.querySelector('.tut-step-placeholder')) {
                              const placeholder = document.createElement('div');
                              placeholder.className = 'tut-step-placeholder';
                              placeholder.innerHTML = `<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg><span>Screenshot coming soon</span>`;
                              parent.appendChild(placeholder);
                            }
                          }}
                        />
                      </div>

                      <div className="tut-step-content">
                        <div className="tut-step-number">Step {activeStep + 1} of {currentSection.steps.length}</div>
                        <h4 className="tut-step-title">{currentSection.steps[activeStep].title}</h4>
                        <p className="tut-step-desc">{currentSection.steps[activeStep].description}</p>

                        {currentSection.steps[activeStep].tip && (
                          <div className="tut-tip">
                            <span className="tut-tip-icon" aria-hidden="true">
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <circle cx="12" cy="12" r="10"/>
                                <line x1="12" y1="16" x2="12" y2="12"/>
                                <line x1="12" y1="8" x2="12.01" y2="8"/>
                              </svg>
                            </span>
                            <span>{currentSection.steps[activeStep].tip}</span>
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="tut-nav">
                      <button
                        className="tut-nav-btn"
                        onClick={handlePrev}
                        disabled={activeStep === 0}
                      >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="15 18 9 12 15 6"/>
                        </svg>
                        Previous
                      </button>
                      <button
                        className="tut-nav-btn primary"
                        onClick={handleNext}
                        disabled={activeStep === currentSection.steps.length - 1}
                      >
                        Next
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="9 18 15 12 9 6"/>
                        </svg>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* ── FAQ Section ── */}
        <h2 className="help-faq-heading">Frequently Asked Questions</h2>

        {FAQ_SECTIONS.map((section, sIdx) => (
          <div key={section.title} className="help-section">
            <h3 className="help-section-title">{section.title}</h3>
            <div className="help-items">
              {section.items.map((item, iIdx) => {
                const key = `${sIdx}-${iIdx}`;
                const isOpen = expandedFaq === key;
                return (
                  <div key={key} className={`help-item${isOpen ? ' open' : ''}`}>
                    <button
                      className="help-question"
                      onClick={() => toggleFaq(key)}
                      aria-expanded={isOpen}
                    >
                      <span className={`help-chevron${isOpen ? ' expanded' : ''}`}>&#9654;</span>
                      <span className="help-question-text">{item.question}</span>
                    </button>
                    {isOpen && (
                      <div className="help-answer">
                        <p>{item.answer}</p>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </DashboardLayout>
  );
}
