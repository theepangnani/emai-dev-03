interface SuggestionChipsProps {
  onChipClick: (text: string) => void;
  currentPage?: string;
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

export function SuggestionChips({ onChipClick, currentPage }: SuggestionChipsProps) {
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
