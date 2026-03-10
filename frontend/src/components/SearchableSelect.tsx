import { useState, useRef, useEffect, useCallback } from 'react';
import './SearchableSelect.css';

export interface SearchableOption {
  id: number;
  label: string;
  sublabel?: string;
}

interface SearchableSelectProps {
  placeholder?: string;
  onSearch: (query: string) => Promise<SearchableOption[]>;
  onSelect: (option: SearchableOption) => void;
  selected?: SearchableOption | null;
  onClear?: () => void;
  disabled?: boolean;
  /** Show a "create new" action at the bottom of results */
  createAction?: { label: string; onClick: () => void };
}

export function SearchableSelect({
  placeholder = 'Search...',
  onSearch,
  onSelect,
  selected,
  onClear,
  disabled,
  createAction,
}: SearchableSelectProps) {
  const [query, setQuery] = useState('');
  const [options, setOptions] = useState<SearchableOption[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const doSearch = useCallback(async (q: string) => {
    setLoading(true);
    try {
      const results = await onSearch(q);
      setOptions(results);
    } catch {
      setOptions([]);
    } finally {
      setLoading(false);
    }
  }, [onSearch]);

  const handleInputChange = (value: string) => {
    setQuery(value);
    setIsOpen(true);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(value), 250);
  };

  const handleSelect = (opt: SearchableOption) => {
    onSelect(opt);
    setQuery('');
    setIsOpen(false);
  };

  const handleClear = () => {
    onClear?.();
    setQuery('');
    inputRef.current?.focus();
  };

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // Load initial options on focus
  const handleFocus = () => {
    if (!selected) {
      setIsOpen(true);
      doSearch(query);
    }
  };

  if (selected) {
    return (
      <div className="searchable-select">
        <div className="searchable-select__selected">
          <div className="searchable-select__selected-info">
            <span className="searchable-select__selected-label">{selected.label}</span>
            {selected.sublabel && <span className="searchable-select__selected-sublabel">{selected.sublabel}</span>}
          </div>
          {!disabled && (
            <button type="button" className="searchable-select__clear" onClick={handleClear} aria-label="Clear selection">
              &times;
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="searchable-select" ref={containerRef}>
      <input
        ref={inputRef}
        type="text"
        className="searchable-select__input"
        value={query}
        onChange={(e) => handleInputChange(e.target.value)}
        onFocus={handleFocus}
        placeholder={placeholder}
        disabled={disabled}
      />
      {isOpen && (
        <div className="searchable-select__dropdown">
          {loading && <div className="searchable-select__loading">Searching...</div>}
          {!loading && options.length === 0 && query && (
            <div className="searchable-select__empty">No results found</div>
          )}
          {!loading && options.map((opt) => (
            <button
              key={opt.id}
              type="button"
              className="searchable-select__option"
              onClick={() => handleSelect(opt)}
            >
              <span className="searchable-select__option-label">{opt.label}</span>
              {opt.sublabel && <span className="searchable-select__option-sublabel">{opt.sublabel}</span>}
            </button>
          ))}
          {createAction && (
            <button
              type="button"
              className={`searchable-select__create-action${!loading && options.length === 0 && query ? ' searchable-select__create-action--prominent' : ''}`}
              onClick={() => { setIsOpen(false); createAction.onClick(); }}
            >
              {createAction.label}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

interface MultiSearchableSelectProps {
  placeholder?: string;
  onSearch: (query: string) => Promise<SearchableOption[]>;
  selected: SearchableOption[];
  onAdd: (option: SearchableOption) => void;
  onRemove: (id: number) => void;
  disabled?: boolean;
}

export function MultiSearchableSelect({
  placeholder = 'Search...',
  onSearch,
  selected,
  onAdd,
  onRemove,
  disabled,
}: MultiSearchableSelectProps) {
  const [query, setQuery] = useState('');
  const [options, setOptions] = useState<SearchableOption[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const selectedIds = new Set(selected.map(s => s.id));

  const doSearch = useCallback(async (q: string) => {
    setLoading(true);
    try {
      const results = await onSearch(q);
      setOptions(results);
    } catch {
      setOptions([]);
    } finally {
      setLoading(false);
    }
  }, [onSearch]);

  const handleInputChange = (value: string) => {
    setQuery(value);
    setIsOpen(true);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(value), 250);
  };

  const handleSelect = (opt: SearchableOption) => {
    if (!selectedIds.has(opt.id)) {
      onAdd(opt);
    }
    setQuery('');
    inputRef.current?.focus();
  };

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleFocus = () => {
    setIsOpen(true);
    doSearch(query);
  };

  const filteredOptions = options.filter(o => !selectedIds.has(o.id));

  return (
    <div className="searchable-select searchable-select--multi" ref={containerRef}>
      {selected.length > 0 && (
        <div className="searchable-select__tags">
          {selected.map((s) => (
            <span key={s.id} className="searchable-select__tag">
              {s.label}
              {!disabled && (
                <button type="button" className="searchable-select__tag-remove" onClick={() => onRemove(s.id)} aria-label={`Remove ${s.label}`}>
                  &times;
                </button>
              )}
            </span>
          ))}
        </div>
      )}
      <input
        ref={inputRef}
        type="text"
        className="searchable-select__input"
        value={query}
        onChange={(e) => handleInputChange(e.target.value)}
        onFocus={handleFocus}
        placeholder={selected.length === 0 ? placeholder : 'Add more...'}
        disabled={disabled}
      />
      {isOpen && (
        <div className="searchable-select__dropdown">
          {loading && <div className="searchable-select__loading">Searching...</div>}
          {!loading && filteredOptions.length === 0 && query && (
            <div className="searchable-select__empty">No results found</div>
          )}
          {!loading && filteredOptions.map((opt) => (
            <button
              key={opt.id}
              type="button"
              className="searchable-select__option"
              onClick={() => handleSelect(opt)}
            >
              <span className="searchable-select__option-label">{opt.label}</span>
              {opt.sublabel && <span className="searchable-select__option-sublabel">{opt.sublabel}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
