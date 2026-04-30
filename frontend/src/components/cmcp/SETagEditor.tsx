/**
 * CB-CMCP-001 M3-A 3A-3 (#4583) — SE-tag editor.
 *
 * Chip-based editor for the curriculum specific-expectation (SE) codes
 * attached to a CMCP artifact. Used inside the M3-A 3A-2 review-queue
 * artifact-detail panel to let teachers add / remove / correct codes
 * during review. The component is render-only — it returns the next
 * code list via ``onChange`` and never calls the PATCH endpoint
 * directly. The parent component owns the persistence step (3A-1's
 * PATCH endpoint).
 *
 * Behaviour
 * ---------
 * - Renders existing ``seCodes`` as chips; each chip has a small ``×``
 *   remove button.
 * - Below the chips, an input field with debounced (300ms) autocomplete
 *   drives a suggestion list, populated from the M0-B curriculum search
 *   endpoint (``GET /api/curriculum/{subject}/search?q=...``).
 * - The autocomplete is gated by ``subjectCode`` — without a subject,
 *   there is no course to search, so the dropdown stays closed and the
 *   helper text explains why.
 * - The ``grade`` prop is accepted for future use (e.g., showing the
 *   subject's grade level in the helper text) but does not currently
 *   filter the API call — the CEG search endpoint does not accept a
 *   grade parameter; subject-level filtering is the agreed M3-A scope.
 * - The user can add a code by:
 *     1. Pressing ``Enter`` on a free-text query (added verbatim — useful
 *        when the teacher knows the code but it's not in the suggestion
 *        list yet).
 *     2. Clicking (or arrow-keying + ``Enter``) a suggestion in the dropdown.
 * - Duplicate codes (case-insensitive) are silently ignored — adding an
 *   already-present code is a no-op.
 * - When ``disabled`` is true, the chips render without the remove button
 *   and the input is hidden entirely. Read-only consumers (e.g., a
 *   future "view artifact" surface) can use the same component.
 *
 * Accessibility
 * -------------
 * - The input has an explicit ``aria-label``.
 * - The suggestion list uses ``role="listbox"`` with ``role="option"``
 *   children, and the input announces ``aria-expanded`` + ``aria-controls``
 *   per the ARIA combobox pattern (1.2 simplified — listbox below input).
 * - Each chip's remove button has an ``aria-label`` that includes the code
 *   so screen readers say "remove SE code A1.1" not just "remove".
 *
 * Tokens / styling
 * ----------------
 * Uses existing global tokens (``--color-*``, ``--radius-*``, ``--font-*``)
 * defined in ``index.css`` / THEME.md. No new tokens are introduced.
 */
import {
  type KeyboardEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import {
  curriculumApi,
  type CurriculumExpectationItem,
} from '../../api/curriculum';
import './SETagEditor.css';

const AUTOCOMPLETE_DEBOUNCE_MS = 300;
// 2 chars is the standard combobox minimum (GitHub label search, Linear,
// MUI Autocomplete). 1 char would explode the response for big subjects
// (MATH covers G1-G8, hundreds of SE codes) and slow the dropdown render.
const MIN_QUERY_LENGTH = 2;

export interface SETagEditorProps {
  /** Current SE codes attached to the artifact. */
  seCodes: string[];
  /** Called with the next code list whenever the user adds/removes a chip. */
  onChange: (codes: string[]) => void;
  /** When true: read-only chips, no input, no remove buttons. */
  disabled?: boolean;
  /** CEG subject code (e.g., "MATH"). Required to enable autocomplete. */
  subjectCode?: string;
  /**
   * Grade level (1-12). Currently informational — the CEG search
   * endpoint does not accept a grade parameter; subject-level filtering
   * is the agreed M3-A scope.
   */
  grade?: number;
}

interface SuggestionRow {
  code: string;
  description: string;
  /** Strand name, used as a faint secondary label in the dropdown. */
  strand: string;
}

/**
 * Flatten the strand-grouped curriculum response into a single
 * ranked-by-API-order list of suggestions.
 */
function flattenStrandGroups(
  groups: { name: string; expectations: CurriculumExpectationItem[] }[],
): SuggestionRow[] {
  const out: SuggestionRow[] = [];
  for (const g of groups) {
    for (const exp of g.expectations) {
      out.push({ code: exp.code, description: exp.description, strand: g.name });
    }
  }
  return out;
}

export function SETagEditor({
  seCodes,
  onChange,
  disabled = false,
  subjectCode,
  grade,
}: SETagEditorProps) {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<SuggestionRow[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Stable lower-cased version for duplicate detection so callers don't
  // have to normalize before passing seCodes in.
  const seCodesLower = useMemo(
    () => new Set(seCodes.map((c) => c.toLowerCase())),
    [seCodes],
  );

  // ── Debounced autocomplete ───────────────────────────────────────────
  // Track the latest in-flight query so out-of-order responses don't
  // overwrite a newer query's results.
  const latestQueryRef = useRef<string>('');

  // Whether the effect should actually fire a search this render.
  const trimmedQuery = query.trim();
  const shouldSearch =
    !disabled && !!subjectCode && trimmedQuery.length >= MIN_QUERY_LENGTH;

  useEffect(() => {
    if (!shouldSearch) {
      // Inactive: nothing to schedule. State resets are handled by the
      // synchronous handlers in addCode/handleKeyDown — calling setState
      // here would trigger cascading renders (react-hooks/set-state-in-effect).
      return;
    }

    // Stamp the latest scheduled query immediately so any in-flight
    // promise compares against a stable, effect-scoped value rather than
    // a value captured later inside the timer callback.
    const myQuery = trimmedQuery;
    latestQueryRef.current = myQuery;

    const timer = setTimeout(() => {
      setIsLoading(true);
      setErrorMsg(null);
      curriculumApi
        .searchExpectations(subjectCode!, myQuery)
        .then((resp) => {
          // Drop stale responses.
          if (latestQueryRef.current !== myQuery) return;
          const rows = flattenStrandGroups(resp.strands);
          setSuggestions(rows);
          setShowDropdown(true);
          setActiveIndex(rows.length > 0 ? 0 : -1);
          setIsLoading(false);
        })
        .catch((err: unknown) => {
          if (latestQueryRef.current !== myQuery) return;
          // 404 from the search endpoint = "no curriculum data for that
          // subject" — render as an empty dropdown with a helper note
          // rather than a hard error.
          const status =
            err && typeof err === 'object' && 'response' in err
              ? // axios shape; narrow defensively
                ((err as { response?: { status?: number } }).response?.status ??
                  null)
              : null;
          if (status === 404) {
            setSuggestions([]);
            setShowDropdown(true);
            setErrorMsg(null);
          } else {
            setSuggestions([]);
            setShowDropdown(true);
            setErrorMsg('Could not load curriculum suggestions.');
          }
          setIsLoading(false);
        });
    }, AUTOCOMPLETE_DEBOUNCE_MS);

    return () => clearTimeout(timer);
  }, [shouldSearch, trimmedQuery, subjectCode]);

  // ── Handlers ─────────────────────────────────────────────────────────
  const addCode = useCallback(
    (code: string) => {
      const trimmed = code.trim();
      if (!trimmed) return;
      if (seCodesLower.has(trimmed.toLowerCase())) {
        // Already present — no-op but still clear the input so the user
        // sees the dropdown reset.
        setQuery('');
        setShowDropdown(false);
        return;
      }
      onChange([...seCodes, trimmed]);
      setQuery('');
      setSuggestions([]);
      setShowDropdown(false);
      setActiveIndex(-1);
    },
    [seCodes, seCodesLower, onChange],
  );

  const removeCode = useCallback(
    (code: string) => {
      onChange(seCodes.filter((c) => c !== code));
    },
    [seCodes, onChange],
  );

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (disabled) return;
    if (e.key === 'Enter') {
      e.preventDefault();
      if (showDropdown && activeIndex >= 0 && suggestions[activeIndex]) {
        addCode(suggestions[activeIndex].code);
      } else if (query.trim()) {
        addCode(query.trim());
      }
    } else if (e.key === 'ArrowDown') {
      if (!showDropdown || suggestions.length === 0) return;
      e.preventDefault();
      setActiveIndex((i) => (i + 1) % suggestions.length);
    } else if (e.key === 'ArrowUp') {
      if (!showDropdown || suggestions.length === 0) return;
      e.preventDefault();
      setActiveIndex((i) =>
        i <= 0 ? suggestions.length - 1 : i - 1,
      );
    } else if (e.key === 'Escape') {
      setShowDropdown(false);
      setActiveIndex(-1);
    }
  };

  const handleQueryChange = (next: string) => {
    setQuery(next);
    // When the user clears the input or backspaces below the min query
    // length, hide the dropdown immediately rather than waiting for a
    // debounced no-op effect run.
    if (next.trim().length < MIN_QUERY_LENGTH) {
      setShowDropdown(false);
      setSuggestions([]);
      setActiveIndex(-1);
      setIsLoading(false);
      setErrorMsg(null);
    }
  };

  const helperText = !subjectCode
    ? 'Subject required to search curriculum.'
    : grade
      ? `Searching ${subjectCode} (grade ${grade}).`
      : `Searching ${subjectCode}.`;

  // ── Render ────────────────────────────────────────────────────────────
  return (
    <div className="cmcp-se-tag-editor" data-testid="cmcp-se-tag-editor">
      <ul className="cmcp-se-tag-editor-chips" role="list">
        {seCodes.map((code) => (
          <li key={code} className="cmcp-se-tag-editor-chip">
            <span className="cmcp-se-tag-editor-chip-code">{code}</span>
            {!disabled && (
              <button
                type="button"
                className="cmcp-se-tag-editor-chip-remove"
                onClick={() => removeCode(code)}
                aria-label={`Remove SE code ${code}`}
              >
                {/* visual × */}
                <span aria-hidden="true">×</span>
              </button>
            )}
          </li>
        ))}
        {seCodes.length === 0 && (
          <li className="cmcp-se-tag-editor-empty" aria-live="polite">
            No SE codes attached.
          </li>
        )}
      </ul>

      {!disabled && (
        <div className="cmcp-se-tag-editor-input-wrap">
          <input
            type="text"
            className="cmcp-se-tag-editor-input"
            value={query}
            onChange={(e) => handleQueryChange(e.target.value)}
            onKeyDown={handleKeyDown}
            onBlur={() => {
              // Defer slightly so a click/mousedown on a suggestion can
              // fire its handler before we tear the dropdown down. The
              // suggestions use onMouseDown + preventDefault, so this
              // delay is the standard combobox idiom for blur-dismiss
              // without losing the click.
              setTimeout(() => {
                setShowDropdown(false);
                setActiveIndex(-1);
              }, 150);
            }}
            placeholder="Add SE code (e.g., A1.1)"
            role="combobox"
            aria-label="Search and add SE code"
            aria-autocomplete="list"
            aria-expanded={showDropdown}
            aria-controls="cmcp-se-tag-editor-listbox"
            disabled={disabled}
          />
          <span className="cmcp-se-tag-editor-helper">{helperText}</span>

          {showDropdown && (
            <ul
              id="cmcp-se-tag-editor-listbox"
              className="cmcp-se-tag-editor-listbox"
              role="listbox"
              aria-label="Curriculum suggestions"
            >
              {isLoading && (
                <li className="cmcp-se-tag-editor-loading" aria-live="polite">
                  Searching…
                </li>
              )}
              {!isLoading && errorMsg && (
                <li className="cmcp-se-tag-editor-error" role="alert">
                  {errorMsg}
                </li>
              )}
              {!isLoading && !errorMsg && suggestions.length === 0 && (
                <li className="cmcp-se-tag-editor-no-results">
                  No matches. Press Enter to add as a free-text code.
                </li>
              )}
              {!isLoading &&
                !errorMsg &&
                suggestions.map((s, i) => (
                  <li
                    key={s.code}
                    role="option"
                    aria-selected={i === activeIndex}
                    className={
                      'cmcp-se-tag-editor-suggestion' +
                      (i === activeIndex
                        ? ' cmcp-se-tag-editor-suggestion-active'
                        : '')
                    }
                    onMouseDown={(e) => {
                      // mousedown (not click) so the input doesn't blur
                      // and dismiss the dropdown before the click lands.
                      e.preventDefault();
                      addCode(s.code);
                    }}
                  >
                    <span className="cmcp-se-tag-editor-suggestion-code">
                      {s.code}
                    </span>
                    <span className="cmcp-se-tag-editor-suggestion-desc">
                      {s.description}
                    </span>
                    <span className="cmcp-se-tag-editor-suggestion-strand">
                      {s.strand}
                    </span>
                  </li>
                ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
