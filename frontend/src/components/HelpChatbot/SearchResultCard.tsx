import { useNavigate } from 'react-router-dom';

interface SearchAction {
  label: string;
  route: string;
}

export interface SearchResult {
  entity_type: string;
  id?: number;
  title: string;
  description?: string;
  actions: SearchAction[];
}

interface SearchResultCardProps {
  results: SearchResult[];
}

const ENTITY_ICONS: Record<string, string> = {
  course: '📚',
  study_guide: '📖',
  task: '✅',
  course_content: '📄',
  faq: '❓',
  note: '📝',
  action: '⚡',
};

export function SearchResultCards({ results }: SearchResultCardProps) {
  const navigate = useNavigate();

  if (!results.length) return null;

  return (
    <div className="search-result-cards">
      {results.map((result, i) => {
        if (result.entity_type === 'summary') {
          return (
            <div key={i} className="search-result-summary">
              <span>{result.title}</span>
              {result.actions[0] && (
                <a
                  href={result.actions[0].route}
                  className="search-result-see-all"
                  onClick={(e) => { e.preventDefault(); navigate(result.actions[0].route); }}
                >
                  {result.actions[0].label} →
                </a>
              )}
            </div>
          );
        }
        return (
          <div key={i} className="search-result-card">
            <div className="search-result-card-header">
              <span className="search-result-icon">
                {ENTITY_ICONS[result.entity_type] ?? '🔍'}
              </span>
              <span className="search-result-title">{result.title}</span>
              <span className="search-result-type">{result.entity_type.replace('_', ' ')}</span>
            </div>
            {result.description && (
              <p className="search-result-description">{result.description}</p>
            )}
            <div className="search-result-actions">
              {result.actions.map((action, j) => (
                <button
                  key={j}
                  className="search-result-action-btn"
                  onClick={() => navigate(action.route)}
                >
                  {action.label}
                </button>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
