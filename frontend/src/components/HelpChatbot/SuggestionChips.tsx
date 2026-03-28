import type { JSX } from 'react';

interface SuggestionChipsProps {
  onChipClick: (text: string) => void;
  currentPage?: string;
  isStudyMode?: boolean;
}

const DEFAULT_CHIPS = [
  'What can this chatbot do?',
  'Getting Started',
  'How do I use Google Classroom?',
  'What are AI Study Tools?',
  'How do I upload materials?',
  'How do I send messages?',
];

const PAGE_CHIPS: Record<string, string[]> = {
  '/tasks': ['How do I create a task?', 'Task reminders', 'Assign tasks to students'],
  '/messages': ['How do I send a message?', 'Message notifications', 'Contact a teacher'],
  '/study': ['How do study guides work?', 'Take a quiz', 'Flashcards'],
  '/courses': ['How do I add a class?', 'Google Classroom sync', 'Class materials'],
  '/course-materials': ['Upload a file', 'Supported file formats', 'Generate study guide'],
  '/my-kids': ['How do I add a child?', 'Link to Google Classroom', 'View grades'],
  '/dashboard': ['Getting Started', 'What can ClassBridge do?', 'Connect Google Classroom'],
  '/help': ['What can this chatbot do?', 'Getting Started', 'How do I use Google Classroom?', 'What are AI Study Tools?'],
};

const STUDY_QA_ACTIONS: { label: string; prompt: string; icon: JSX.Element }[] = [
  {
    label: 'Summarize key concepts',
    prompt: 'Summarize key concepts',
    icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>,
  },
  {
    label: 'Quiz me on this topic',
    prompt: 'Quiz me on this topic',
    icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>,
  },
  {
    label: 'Explain the main ideas',
    prompt: 'Explain the main ideas',
    icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2 3h6a4 4 0 014 4v14a3 3 0 00-3-3H2z"/><path d="M22 3h-6a4 4 0 00-4 4v14a3 3 0 013-3h7z"/></svg>,
  },
  {
    label: 'Practice questions',
    prompt: 'Give me practice questions',
    icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>,
  },
  {
    label: 'Generate study guide',
    prompt: 'Generate a study guide from this content',
    icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><path d="M8 13h2M8 17h2M12 13h4M12 17h4"/></svg>,
  },
];

export function SuggestionChips({ onChipClick, currentPage, isStudyMode }: SuggestionChipsProps) {
  if (isStudyMode) {
    return (
      <div className="study-qa-actions">
        {STUDY_QA_ACTIONS.map((action) => (
          <button
            key={action.label}
            className="study-qa-action-row"
            onClick={() => onChipClick(action.prompt)}
          >
            <span className="study-qa-action-icon">{action.icon}</span>
            <span className="study-qa-action-label">{action.label}</span>
            <svg className="study-qa-action-arrow" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
          </button>
        ))}
      </div>
    );
  }

  const chips = (currentPage && PAGE_CHIPS[currentPage]) || DEFAULT_CHIPS;

  return (
    <div className="help-chatbot-chips">
      {chips.map((chip) => (
        <button
          key={chip}
          className="help-chatbot-chip"
          onClick={() => onChipClick(chip)}
        >
          {chip}
        </button>
      ))}
    </div>
  );
}
