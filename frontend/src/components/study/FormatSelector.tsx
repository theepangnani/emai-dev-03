import './FormatSelector.css';

export type StudyFormat = 'study_guide' | 'quiz' | 'flashcards' | 'mind_map';

interface FormatOption {
  key: StudyFormat;
  label: string;
  description: string;
  icon: React.ReactNode;
  comingSoon?: boolean;
}

interface FormatSelectorProps {
  selected: StudyFormat;
  onSelect: (format: StudyFormat) => void;
  disabled?: StudyFormat[];
}

function BookIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M4 4h4l2 2h8a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6a2 2 0 012-2z" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M8 12h8M8 15h5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M8 12l3 3 5-6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

function CardsIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="2" y="5" width="14" height="10" rx="2" stroke="currentColor" strokeWidth="1.5"/>
      <rect x="8" y="9" width="14" height="10" rx="2" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M11 13h8M11 16h5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    </svg>
  );
}

function MindMapIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.5"/>
      <circle cx="5" cy="6" r="2" stroke="currentColor" strokeWidth="1.3"/>
      <circle cx="19" cy="6" r="2" stroke="currentColor" strokeWidth="1.3"/>
      <circle cx="5" cy="18" r="2" stroke="currentColor" strokeWidth="1.3"/>
      <circle cx="19" cy="18" r="2" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M9.5 10L6.5 7.5M14.5 10l3-2.5M9.5 14l-3 2.5M14.5 14l3 2.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
    </svg>
  );
}

const FORMAT_OPTIONS: FormatOption[] = [
  {
    key: 'study_guide',
    label: 'Study Guide',
    description: 'Comprehensive notes and explanations',
    icon: <BookIcon />,
  },
  {
    key: 'quiz',
    label: 'Quiz',
    description: 'Test your knowledge with questions',
    icon: <CheckIcon />,
  },
  {
    key: 'flashcards',
    label: 'Flashcards',
    description: 'Quick review with flip cards',
    icon: <CardsIcon />,
  },
  {
    key: 'mind_map',
    label: 'Mind Map',
    description: 'Visual connections between concepts',
    icon: <MindMapIcon />,
    comingSoon: true,
  },
];

export function FormatSelector({ selected, onSelect, disabled = [] }: FormatSelectorProps) {
  return (
    <div className="format-selector" role="radiogroup" aria-label="Choose study format">
      <h3 className="format-selector-title">Learn Your Way</h3>
      <p className="format-selector-subtitle">Choose how you want to study this material</p>
      <div className="format-selector-grid">
        {FORMAT_OPTIONS.map((opt) => {
          const isDisabled = disabled.includes(opt.key) || opt.comingSoon;
          const isSelected = selected === opt.key;
          return (
            <button
              key={opt.key}
              className={`format-card${isSelected ? ' selected' : ''}${isDisabled ? ' disabled' : ''}`}
              onClick={() => !isDisabled && onSelect(opt.key)}
              disabled={isDisabled}
              role="radio"
              aria-checked={isSelected}
              aria-label={`${opt.label}${opt.comingSoon ? ' (coming soon)' : ''}`}
            >
              <div className="format-card-icon">{opt.icon}</div>
              <div className="format-card-label">{opt.label}</div>
              <div className="format-card-desc">{opt.description}</div>
              {opt.comingSoon && <span className="format-card-badge">Coming Soon</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
}
