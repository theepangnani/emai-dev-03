import { useState, useRef, useEffect, useCallback, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { searchApi, type SearchResponse, type SearchResultGroup, type SearchResultItem } from '../api/client';
import './GlobalSearch.css';

const TYPE_ICONS: Record<string, string> = {
  child: '\uD83D\uDC66',          // boy
  course: '\uD83C\uDF93',         // graduation cap
  assignment: '\uD83D\uDCDD',     // memo
  study_guide: '\uD83D\uDCD6',    // open book
  task: '\uD83D\uDCCB',           // clipboard
  course_content: '\uD83D\uDCC4', // page
  faq: '\u2753',                   // question mark
  note: '\uD83D\uDCDD',           // memo/note
};

function highlightMatch(text: string, term: string): ReactNode {
  if (!term || term.length < 2) return text;
  const idx = text.toLowerCase().indexOf(term.toLowerCase());
  if (idx < 0) return text;
  return (
    <>
      {text.slice(0, idx)}
      <mark className="global-search-highlight">{text.slice(idx, idx + term.length)}</mark>
      {text.slice(idx + term.length)}
    </>
  );
}

/** Flatten grouped results into a single ordered list for keyboard nav */
function flattenResults(groups: SearchResultGroup[]): SearchResultItem[] {
  const items: SearchResultItem[] = [];
  for (const group of groups) {
    for (const item of group.items) {
      items.push(item);
    }
  }
  return items;
}

export function GlobalSearch() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const listRef = useRef<HTMLDivElement>(null);

  const flatItems = results ? flattenResults(results.groups) : [];

  // Debounced search
  const doSearch = useCallback(async (term: string) => {
    if (term.length < 2) {
      setResults(null);
      return;
    }
    setLoading(true);
    try {
      const data = await searchApi.search(term);
      setResults(data);
      setActiveIndex(-1);
    } catch {
      setResults(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleChange = (value: string) => {
    setQuery(value);
    setActiveIndex(-1);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (value.trim().length < 2) {
      setResults(null);
      return;
    }
    debounceRef.current = setTimeout(() => doSearch(value.trim()), 300);
  };

  const closeModal = useCallback(() => {
    setOpen(false);
    setQuery('');
    setResults(null);
    setActiveIndex(-1);
  }, []);

  const openModal = useCallback(() => {
    setOpen(true);
    setTimeout(() => inputRef.current?.focus(), 50);
  }, []);

  const handleResultClick = useCallback((url: string) => {
    closeModal();
    navigate(url);
  }, [closeModal, navigate]);

  // Global keyboard shortcut: Ctrl+K / Cmd+K
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        if (open) {
          closeModal();
        } else {
          openModal();
        }
      }
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [open, closeModal, openModal]);

  // Keyboard navigation inside modal
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      closeModal();
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex(prev => Math.min(prev + 1, flatItems.length - 1));
      return;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex(prev => Math.max(prev - 1, -1));
      return;
    }
    if (e.key === 'Enter' && activeIndex >= 0 && activeIndex < flatItems.length) {
      e.preventDefault();
      handleResultClick(flatItems[activeIndex].url);
    }
  };

  // Scroll active item into view
  useEffect(() => {
    if (activeIndex < 0 || !listRef.current) return;
    const items = listRef.current.querySelectorAll('[data-search-item]');
    items[activeIndex]?.scrollIntoView({ block: 'nearest' });
  }, [activeIndex]);

  const hasResults = results && results.groups.some(g => g.items.length > 0);
  let globalIdx = -1; // tracks position across groups for keyboard nav

  return (
    <>
      {/* Trigger button in header */}
      <button
        className="global-search-trigger"
        onClick={openModal}
        aria-label="Search ClassBridge (Ctrl+K)"
      >
        <span className="global-search-trigger-icon" aria-hidden="true">&#128269;</span>
        <span className="global-search-trigger-text">Search...</span>
        <kbd className="global-search-kbd">Ctrl+K</kbd>
      </button>

      {/* Command Palette Modal */}
      {open && (
        <div className="command-palette-overlay" onClick={closeModal}>
          <div
            className="command-palette"
            onClick={e => e.stopPropagation()}
            onKeyDown={handleKeyDown}
            role="dialog"
            aria-label="Search ClassBridge"
          >
            <div className="command-palette-input-wrap">
              <span className="command-palette-search-icon" aria-hidden="true">&#128269;</span>
              <label htmlFor="command-palette-input" className="sr-only">Search ClassBridge</label>
              <input
                ref={inputRef}
                id="command-palette-input"
                type="text"
                className="command-palette-input"
                placeholder="Search children, courses, assignments, tasks..."
                value={query}
                onChange={e => handleChange(e.target.value)}
                autoComplete="off"
              />
              {loading && <span className="global-search-spinner" />}
              <kbd className="command-palette-esc" onClick={closeModal}>ESC</kbd>
            </div>

            <div className="command-palette-results" ref={listRef}>
              {query.length >= 2 && !hasResults && !loading && (
                <div className="global-search-empty">No results for &ldquo;{query}&rdquo;</div>
              )}
              {query.length < 2 && (
                <div className="command-palette-hint">
                  Type at least 2 characters to search
                </div>
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
                    {group.items.map((item) => {
                      globalIdx++;
                      const idx = globalIdx;
                      return (
                        <button
                          key={`${item.entity_type}-${item.id}`}
                          className={`global-search-item${idx === activeIndex ? ' active' : ''}`}
                          data-search-item
                          onClick={() => handleResultClick(item.url)}
                          onMouseEnter={() => setActiveIndex(idx)}
                        >
                          <span className="global-search-item-icon" aria-hidden="true">{TYPE_ICONS[item.entity_type] || ''}</span>
                          <div className="global-search-item-text">
                            <span className="global-search-item-title">{highlightMatch(item.title, query)}</span>
                            {item.subtitle && (
                              <span className="global-search-item-subtitle">{highlightMatch(item.subtitle, query)}</span>
                            )}
                          </div>
                          {idx === activeIndex && (
                            <span className="global-search-item-enter" aria-hidden="true">Enter</span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                ) : null
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
