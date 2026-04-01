import './StudyGuideSuggestionChips.css';

interface SuggestionTopic {
  label: string;
  description: string;
}

interface StudyGuideSuggestionChipsProps {
  topics: SuggestionTopic[];
  onTopicClick: (topic: SuggestionTopic) => void;
  disabled?: boolean;
  generatingTopic?: string | null;
}

export default function StudyGuideSuggestionChips({
  topics,
  onTopicClick,
  disabled = false,
  generatingTopic = null,
}: StudyGuideSuggestionChipsProps) {
  if (!topics.length) return null;

  const isAnyGenerating = !!generatingTopic;

  return (
    <div className="sg-suggestion-section">
      <div className="sg-suggestion-header">
        <span className="sg-suggestion-icon">{'\u{1F50D}'}</span>
        <span>Explore topics in detail</span>
      </div>
      <div className="sg-suggestion-chips">
        {topics.map((topic) => {
          const isThis = generatingTopic === topic.label;
          return (
            <button
              key={topic.label}
              className={`sg-suggestion-chip ${isThis ? 'sg-suggestion-chip--generating' : ''} ${topic.label === 'Ask Bot' ? 'sg-suggestion-chip--ask-bot' : ''}`}
              onClick={() => onTopicClick(topic)}
              disabled={topic.label === 'Ask Bot' ? false : (disabled || isAnyGenerating)}
              title={topic.description}
              aria-label={topic.label === 'Ask Bot' ? 'Ask the AI chatbot' : `Explore: ${topic.label}`}
            >
              {isThis && <span className="sg-chip-spinner" />}
              <span className="sg-chip-label">{topic.label === 'Ask Bot' ? '\u{1F916} Ask Bot' : topic.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export type { SuggestionTopic };
