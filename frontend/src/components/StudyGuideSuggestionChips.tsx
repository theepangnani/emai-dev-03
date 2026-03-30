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
              className={`sg-suggestion-chip ${isThis ? 'sg-suggestion-chip--generating' : ''}`}
              onClick={() => onTopicClick(topic)}
              disabled={disabled || isAnyGenerating}
              title={topic.description}
              aria-label={`Explore: ${topic.label}`}
            >
              {isThis && <span className="sg-chip-spinner" />}
              <span className="sg-chip-label">{topic.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export type { SuggestionTopic };
