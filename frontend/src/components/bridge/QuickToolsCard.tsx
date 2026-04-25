/**
 * CB-BRIDGE-HF Stream D — Quick Tools strip (#4130, #4133).
 *
 * Restores four discoverable per-kid actions that the Bridge re-skin
 * (PR #4123) removed from the bottom strip:
 *   - Help My Kid    → /ai-tools
 *   - View Tasks     → /tasks?student_id=<selectedChild>
 *   - Request Study  → opens StudyRequestModal
 *   - Report Cards   → /school-report-cards
 *
 * Rendered between the management grid and the insight grid in the
 * selected-kid branch of MyKidsPage. Bridge-styled, four-column on
 * desktop, single column on mobile (≤720px).
 */

interface QuickToolsCardProps {
  onHelpMyKid: () => void;
  onViewTasks: () => void;
  onRequestStudy: () => void;
  onReportCards: () => void;
}

interface Tool {
  key: string;
  icon: string;
  title: string;
  description: string;
  onClick: () => void;
}

export function QuickToolsCard({
  onHelpMyKid,
  onViewTasks,
  onRequestStudy,
  onReportCards,
}: QuickToolsCardProps) {
  const tools: Tool[] = [
    {
      key: 'help',
      icon: '✨',
      title: 'Help My Kid',
      description: 'Open the AI study tools to make flashcards, quizzes, and notes.',
      onClick: onHelpMyKid,
    },
    {
      key: 'tasks',
      icon: '✓',
      title: 'View Tasks',
      description: "Open this kid's task list, filtered by them.",
      onClick: onViewTasks,
    },
    {
      key: 'request',
      icon: '📚',
      title: 'Request Study',
      description: 'Suggest a topic for your child to review this week.',
      onClick: onRequestStudy,
    },
    {
      key: 'reports',
      icon: '📄',
      title: 'Report Cards',
      description: 'View school report cards and term summaries.',
      onClick: onReportCards,
    },
  ];

  return (
    <>
      <div className="bridge-section-head">
        <h2>Quick tools</h2>
        <span className="bridge-section-meta">4 · shortcuts</span>
      </div>
      <div className="bridge-quicktools">
        {tools.map((t) => (
          <button
            key={t.key}
            type="button"
            className="bridge-quicktool"
            onClick={t.onClick}
          >
            <span className="bridge-quicktool-icon" aria-hidden="true">{t.icon}</span>
            <span className="bridge-quicktool-body">
              <span className="bridge-quicktool-title">{t.title}</span>
              <span className="bridge-quicktool-desc">{t.description}</span>
            </span>
            <span className="bridge-quicktool-chev" aria-hidden="true">→</span>
          </button>
        ))}
      </div>
    </>
  );
}
