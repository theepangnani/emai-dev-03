"""help_articles: seed data (#1420)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    try:
        if "help_articles" in inspector.get_table_names():
            seed_articles = [
                    ("getting-started", "Getting Started with ClassBridge", "getting-started",
                     "## Welcome to ClassBridge\n\nClassBridge is an AI-powered education platform that connects parents, students, teachers, and administrators.\n\n### First Steps\n\n1. **Create your account** -- Sign up with your email or Google account\n2. **Complete onboarding** -- Select your role and fill in your profile\n3. **Connect Google Classroom** (optional) -- Import your classes and assignments automatically\n4. **Explore the dashboard** -- See your courses, tasks, and upcoming assignments\n\n### Key Features\n\n- **AI Study Tools** -- Generate study guides, quizzes, and flashcards from your course materials\n- **Task Management** -- Create and track tasks with due dates and reminders\n- **Messaging** -- Communicate with teachers and parents directly\n- **Google Classroom Sync** -- Automatically import courses, assignments, and grades",
                     None, 1),
                    ("parent-guide", "Parent Guide", "parent-guide",
                     "## Parent Guide\n\nAs a parent on ClassBridge, you can monitor your children's academic progress and communicate with their teachers.\n\n### Adding Your Child\n\n1. From your dashboard, click the **+** button on the child pills row\n2. Enter your child's name (email is optional)\n3. If you provide an email, they'll receive an invite to set their own password\n\n### Connecting Google Classroom\n\nClick **Connect Google Classroom** on your dashboard to link your Google account. This imports your child's courses, assignments, and grades automatically.\n\n### Creating Study Materials\n\n1. Click **Upload Documents** to add PDFs, Word docs, or PowerPoint files\n2. Select which AI tools to generate: Study Guide, Quiz, or Flashcards\n3. Review and print materials from the course material tabs\n\n### Communicating with Teachers\n\nGo to **Messages** in the sidebar to start a conversation with any linked teacher.",
                     "parent", 2),
                    ("student-guide", "Student Guide", "student-guide",
                     "## Student Guide\n\nAs a student, ClassBridge helps you organize your studies and use AI-powered tools to learn more effectively.\n\n### Your Dashboard\n\nYour dashboard shows urgency pills (overdue/due today), quick actions, and a timeline of upcoming assignments and tasks.\n\n### Study Hub\n\n1. **Create or join a course** from the Study Hub\n2. **Upload materials** -- PDFs, Word docs, or images of handouts\n3. **Generate AI study tools** -- Study guides, quizzes, and flashcards\n\n### AI Study Tools\n\n- **Study Guides** -- AI creates structured summaries with key concepts\n- **Practice Quizzes** -- Choose Easy, Medium, or Hard difficulty with instant feedback\n- **Flashcards** -- Flip cards generated from your material\n\n### Staying Organized\n\n- Use the **Tasks** page to track assignments and personal tasks\n- Take **Notes** while viewing study materials (auto-saved)\n- Use the **Calendar** to see all due dates at a glance",
                     "student", 3),
                    ("teacher-guide", "Teacher Guide", "teacher-guide",
                     "## Teacher Guide\n\nClassBridge helps you manage your classroom, share materials, and communicate with parents.\n\n### Setting Up Courses\n\n1. Click **Create Course** from your dashboard or sidebar\n2. Enter course name, subject, and description\n3. Optionally connect Google Classroom to import existing courses\n\n### Managing Students\n\nOpen a course and click **Add Student** in the Student Roster section. Students receive an invite if they're not on ClassBridge yet.\n\n### Sharing Materials\n\nUpload course materials from **Course Materials** in the sidebar. You can generate AI study tools during upload to help students.\n\n### Communication\n\n- Use **Messages** to communicate with parents of enrolled students\n- Check **Teacher Communications** for synced emails and announcements",
                     "teacher", 4),
                    ("ai-study-tools", "AI Study Tools", "ai-tools",
                     "## AI Study Tools\n\nClassBridge uses AI to generate personalized study materials from your course content.\n\n### Study Guides\n\nAI creates structured summaries highlighting key concepts, definitions, and important points. You can provide a focus prompt to target specific topics.\n\n### Practice Quizzes\n\nGenerate multiple-choice quizzes at Easy, Medium, or Hard difficulty. Get instant feedback on each answer and track your score history over time.\n\n### Flashcards\n\nAI generates flip cards from your material. Click to flip, use arrow keys to navigate, and shuffle for variety.\n\n### Tips for Best Results\n\n- Upload clear, text-based documents (PDFs, Word docs)\n- Use focus prompts like \"Focus on Chapter 5 vocabulary\"\n- Generation happens in the background -- keep working while AI creates materials\n- Each generation uses AI credits from your monthly allowance",
                     None, 5),
                    ("google-classroom", "Google Classroom Integration", "getting-started",
                     "## Google Classroom Integration\n\nClassBridge integrates with Google Classroom to automatically sync your courses, assignments, and grades.\n\n### Connecting Your Account\n\n1. Go to your Dashboard\n2. Click **Connect Google Classroom**\n3. Sign in with your Google account and grant permissions\n4. Your classes and assignments sync automatically\n\n### What Gets Synced\n\n- **Courses** -- All your Google Classroom courses\n- **Assignments** -- Due dates, descriptions, and points\n- **Grades** -- Student grades and submission status\n- **Materials** -- Course materials and announcements\n\n### Troubleshooting\n\n- If sync fails, try clicking the sync button again\n- If authorization expired, reconnect from the Dashboard\n- You can connect multiple Google accounts (personal + school)",
                     None, 6),
                    ("account-settings", "Account & Settings", "account-settings",
                     "## Account & Settings\n\n### Changing Your Password\n\nUse the **Forgot Password** link on the login page to receive a reset link via email.\n\n### Notification Preferences\n\nClick the bell icon to view notifications. Email notifications are sent automatically for important events like new messages and assignment reminders.\n\n### AI Usage Credits\n\nEach user has a monthly AI credit allowance. Credits are used when generating study guides, quizzes, and flashcards. You can request additional credits from the AI Usage page.\n\n### Data Privacy\n\nYou can request a full export of your data or delete your account from Account Settings. Account deletion has a 30-day grace period.\n\n### Multi-Role Users\n\nIf you have multiple roles (e.g., teacher and parent), click your role badge to switch between views.",
                     None, 7),
                    ("messaging", "Messaging & Communication", "communication",
                     "## Messaging & Communication\n\nClassBridge provides built-in messaging between parents, teachers, and administrators.\n\n### Sending Messages\n\n1. Go to **Messages** in the sidebar\n2. Click **New Message**\n3. Select a recipient from connected teachers or parents\n4. Type your message and send\n\n### Notifications\n\nYou'll receive in-app and email notifications when someone replies to your messages.\n\n### Teacher Communications\n\nTeachers can view synced emails and announcements with AI-generated summaries in the **Teacher Communications** section.\n\n### Tips\n\n- Messages are organized by conversation\n- You can message any teacher linked to your child\n- Teachers can message parents of enrolled students",
                     None, 8),
                    ("tasks-calendar", "Tasks & Calendar", "account-settings",
                     "## Tasks & Calendar\n\n### Creating Tasks\n\n1. Go to **Tasks** in the sidebar\n2. Click the **+** button to create a new task\n3. Set a title, description, due date, and priority\n4. Optionally assign tasks to children (parents) or link to courses\n\n### Task Views\n\nTasks are grouped by urgency: Overdue, Due Today, This Week, and Later.\n\n### Calendar\n\nThe calendar shows all assignments and tasks. Switch between Month, Week, 3-Day, and Day views. Drag tasks to reschedule them.\n\n### Reminders\n\nClassBridge sends automatic reminders before task due dates. Configure reminder timing in your account settings.",
                     None, 9),
                ]
            inserted = 0
            for slug, title, category, content, role, order in seed_articles:
                exists = conn.execute(text("SELECT 1 FROM help_articles WHERE slug = :slug"), {"slug": slug}).fetchone()
                if not exists:
                    conn.execute(text(
                        "INSERT INTO help_articles (slug, title, category, content, role, display_order) "
                        "VALUES (:slug, :title, :category, :content, :role, :order)"
                    ), {"slug": slug, "title": title, "category": category, "content": content, "role": role, "order": order})
                    inserted += 1
            if inserted:
                conn.commit()
                logger.info("Seeded %d missing help_articles (#1420)", inserted)
    except Exception as e:
        conn.rollback()
        logger.error("Failed to seed help_articles: %s", e)
