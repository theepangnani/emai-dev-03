import { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { searchApi, type SearchResponse, type SearchResultGroup } from '../api/client';
import './GlobalSearch.css';

const TYPE_ICONS: Record<string, string> = {
  course: '\uD83C\uDF93',        // 🎓
  study_guide: '\uD83D\uDCD6',   // 📖
  task: '\uD83D\uDCCB',          // 📋
  course_content: '\uD83D\uDCC4', // 📄
};

export function GlobalSearch() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  // Debounced search
  const doSearch = useCallback(async (term: string) => {
    if (term.length < 2) {
      setResults(null);
      setOpen(false);
      return;
    }
    setLoading(true);
    try {
      const data = await searchApi.search(term);
      setResults(data);
      setOpen(true);
    } catch {
      setResults(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleChange = (value: string) => {
    setQuery(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (value.trim().length < 2) {
      setResults(null);
      setOpen(false);
      return;
    }
    debounceRef.current = setTimeout(() => doSearch(value.trim()), 300);
  };

  // Click outside to close
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Keyboard shortcut: Ctrl+K / Cmd+K
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        inputRef.current?.focus();
      }
      if (e.key === 'Escape') {
        setOpen(false);
        inputRef.current?.blur();
      }
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, []);

  const handleResultClick = (url: string) => {
    setOpen(false);
    setQuery('');
    setResults(null);
    navigate(url);
  };

  const hasResults = results && results.groups.some(g => g.items.length > 0);

  return (
    <div className="global-search" ref={containerRef}>
      <div className="global-search-input-wrap">
        <span className="global-search-icon">&#128269;</span>
        <input
          ref={inputRef}
          type="text"
          className="global-search-input"
          placeholder="Search ClassBridge... (Ctrl+K)"
          value={query}
          onChange={(e) => handleChange(e.target.value)}
          onFocus={() => { if (results && query.length >= 2) setOpen(true); }}
        />
        {loading && <span className="global-search-spinner" />}
      </div>

      {open && (
        <div className="global-search-dropdown">
          {!hasResults && !loading && (
            <div className="global-search-empty">No results for &ldquo;{query}&rdquo;</div>
          )}
          {results?.groups.map((group: SearchResultGroup) =>
            group.items.length > 0 ? (
              <div key={group.entity_type} className="global-search-group">
                <div className="global-search-group-label">
                  {TYPE_ICONS[group.entity_type] || ''} {group.label}
                  {group.total > group.items.length && (
                    <span className="global-search-group-count"> ({group.total})</span>
                  )}
                </div>
                {group.items.map((item) => (
                  <button
                    key={`${item.entity_type}-${item.id}`}
                    className="global-search-item"
                    onClick={() => handleResultClick(item.url)}
                  >
                    <span className="global-search-item-icon">{TYPE_ICONS[item.entity_type] || ''}</span>
                    <div className="global-search-item-text">
                      <span className="global-search-item-title">{item.title}</span>
                      {item.subtitle && (
                        <span className="global-search-item-subtitle">{item.subtitle}</span>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            ) : null
          )}
        </div>
      )}
    </div>
  );
}
