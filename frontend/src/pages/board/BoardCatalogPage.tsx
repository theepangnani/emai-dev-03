/**
 * CB-CMCP-001 M3-H 3H-2 (#4666) — Board catalog browse page.
 *
 * Route: /board/catalog
 * RBAC: BOARD_ADMIN + ADMIN (gated by `<ProtectedRoute>` in App.tsx).
 *       Backend `/api/board/{board_id}/catalog` (3E-1, PR #4671) and
 *       `/api/board/{board_id}/catalog/export.csv` (3E-3, PR #4674)
 *       enforce the same gate independently — the route gate is purely UX.
 *
 * Surface
 * -------
 * Sortable table of APPROVED artifacts for the caller's board with subject /
 * grade / state filters and an "Export CSV" button. The board id resolution
 * mirrors 3H-1's BoardDashboardPage:
 *   - BOARD_ADMIN  → uses their stamped `board_id` from the User profile
 *   - ADMIN        → may supply a `?board_id=…` query param OR enter a
 *                    board id via the picker (committed on submit, not
 *                    per-keystroke)
 *
 * Data flow
 * ---------
 *   GET  /api/board/{board_id}/catalog?... → paginated artifact rows
 *   POST /api/board/{board_id}/catalog/export.csv → signed download_url
 *
 * Pagination
 * ----------
 * Cursor-based — the same `next_cursor` contract as 3E-1's MCP-aligned
 * surface. We keep a stack of cursors so the user can step backwards
 * through pages they've already loaded without re-issuing the original
 * (cursor=None) query.
 *
 * Out of scope (per #4666)
 * ------------------------
 * - Coverage heatmap (3H-1's BoardDashboardPage already owns it).
 * - Bulk artifact actions / inline state edits — read-only for now.
 * - Server-side sort: the page sorts the current page client-side; full
 *   cross-page sort would require a server contract change.
 */
import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router-dom';

import { useAuth } from '../../context/AuthContext';
import { useFeatureFlagState } from '../../hooks/useFeatureToggle';
import {
  boardCatalogApi,
  type BoardCatalogArtifact,
  type BoardCatalogParams,
} from '../../api/boardCatalog';

import './BoardDashboardPage.css';
import './BoardCatalogPage.css';

const PAGE_LIMIT = 50;

type SortField = 'id' | 'title' | 'content_type' | 'subject_code' | 'grade' | 'created_at';
type SortDir = 'asc' | 'desc';

const SORT_LABELS: Record<SortField, string> = {
  id: 'ID',
  title: 'Title',
  content_type: 'Type',
  subject_code: 'Subject',
  grade: 'Grade',
  created_at: 'Created',
};

function userBoardId(user: ReturnType<typeof useAuth>['user']): string | null {
  if (!user) return null;
  const candidate = (user as unknown as { board_id?: string | null })
    .board_id;
  if (typeof candidate === 'string' && candidate.length > 0) return candidate;
  return null;
}

function isAdmin(user: ReturnType<typeof useAuth>['user']): boolean {
  if (!user) return false;
  const role = user.role;
  const roles = user.roles ?? [];
  return roles.includes('admin') || roles.includes('ADMIN') || role === 'admin' || role === 'ADMIN';
}

function compareValues(
  a: BoardCatalogArtifact,
  b: BoardCatalogArtifact,
  field: SortField,
  dir: SortDir,
): number {
  const av = a[field];
  const bv = b[field];
  // Treat null / undefined as the largest values so they sort to the end
  // for ascending, top for descending.
  const aNull = av === null || av === undefined;
  const bNull = bv === null || bv === undefined;
  if (aNull && bNull) return 0;
  if (aNull) return 1;
  if (bNull) return -1;

  let cmp: number;
  if (typeof av === 'number' && typeof bv === 'number') {
    cmp = av - bv;
  } else {
    cmp = String(av).localeCompare(String(bv));
  }
  return dir === 'asc' ? cmp : -cmp;
}

export function BoardCatalogPage() {
  const { user } = useAuth();
  const { enabled: cmcpEnabled, isLoading: flagLoading } =
    useFeatureFlagState('cmcp.enabled');
  const [searchParams] = useSearchParams();

  // Admin board picker — same decoupled-state pattern as 3H-1 so the
  // backend doesn't see a per-keystroke firehose.
  const [adminBoardInput, setAdminBoardInput] = useState<string>('');
  const [appliedAdminBoard, setAppliedAdminBoard] = useState<string>('');

  // Filter inputs (controlled) vs. applied filters (driving the query).
  // Decoupled for the same reason as the board picker — a 4-character
  // grade typo shouldn't be 4 separate API calls.
  const [subjectInput, setSubjectInput] = useState<string>('');
  const [gradeInput, setGradeInput] = useState<string>('');
  const [contentTypeInput, setContentTypeInput] = useState<string>('');
  const [appliedFilters, setAppliedFilters] = useState<{
    subject_code: string | null;
    grade: number | null;
    content_type: string | null;
  }>({ subject_code: null, grade: null, content_type: null });

  // Cursor stack for back-navigation — top of stack is the cursor that
  // produced the current page. `null` means "first page".
  const [cursorStack, setCursorStack] = useState<(string | null)[]>([null]);

  // Sort state — current page only (server returns id-desc by default).
  const [sortField, setSortField] = useState<SortField>('id');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  // Export state — separate from the table query so a slow CSV doesn't
  // block reading the table. ``exportFallbackUrl`` carries the
  // signed-URL when ``window.open`` was popup-blocked (Safari etc. block
  // popups opened after an async round-trip even with `noopener`); the
  // user can then click the surfaced link directly to download.
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportInFlight, setExportInFlight] = useState<boolean>(false);
  const [exportFallbackUrl, setExportFallbackUrl] = useState<string | null>(
    null,
  );

  const adminBoardOverride = searchParams.get('board_id');
  const profileBoard = userBoardId(user);
  const userIsAdmin = isAdmin(user);

  const adminFallback = userIsAdmin
    ? (adminBoardOverride ?? (appliedAdminBoard.trim() || null))
    : null;
  const effectiveBoardId = profileBoard ?? adminFallback;

  const queryEnabled = cmcpEnabled && Boolean(effectiveBoardId);

  const currentCursor = cursorStack[cursorStack.length - 1] ?? null;

  const queryParams: BoardCatalogParams = useMemo(
    () => ({
      cursor: currentCursor ?? null,
      limit: PAGE_LIMIT,
      subject_code: appliedFilters.subject_code,
      grade: appliedFilters.grade,
      content_type: appliedFilters.content_type,
    }),
    [
      currentCursor,
      appliedFilters.subject_code,
      appliedFilters.grade,
      appliedFilters.content_type,
    ],
  );

  const catalogQuery = useQuery({
    queryKey: ['board-catalog-browse', effectiveBoardId, queryParams],
    queryFn: () =>
      boardCatalogApi.getCatalog(effectiveBoardId as string, queryParams),
    enabled: queryEnabled,
  });

  const sortedArtifacts = useMemo(() => {
    const artifacts = catalogQuery.data?.artifacts ?? [];
    return [...artifacts].sort((a, b) => compareValues(a, b, sortField, sortDir));
  }, [catalogQuery.data?.artifacts, sortField, sortDir]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir('asc');
    }
  };

  const handleApplyFilters = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedSubject = subjectInput.trim();
    const trimmedGrade = gradeInput.trim();
    const trimmedContent = contentTypeInput.trim();
    let parsedGrade: number | null = null;
    if (trimmedGrade !== '') {
      const n = Number(trimmedGrade);
      // Quietly drop unparseable grades — the input itself is type=number
      // so the user normally can't enter junk, but be defensive.
      if (Number.isFinite(n) && Number.isInteger(n)) {
        parsedGrade = n;
      }
    }
    setAppliedFilters({
      subject_code: trimmedSubject === '' ? null : trimmedSubject,
      grade: parsedGrade,
      content_type: trimmedContent === '' ? null : trimmedContent,
    });
    // Filter change resets pagination — stale cursors point to a window
    // computed under different filters.
    setCursorStack([null]);
  };

  const handleClearFilters = () => {
    setSubjectInput('');
    setGradeInput('');
    setContentTypeInput('');
    setAppliedFilters({ subject_code: null, grade: null, content_type: null });
    setCursorStack([null]);
  };

  const handleNextPage = () => {
    const next = catalogQuery.data?.next_cursor ?? null;
    if (!next) return;
    setCursorStack((s) => [...s, next]);
  };

  const handlePrevPage = () => {
    setCursorStack((s) => (s.length > 1 ? s.slice(0, -1) : s));
  };

  const handleExport = async () => {
    if (!effectiveBoardId) return;
    setExportError(null);
    setExportFallbackUrl(null);
    setExportInFlight(true);
    try {
      const resp = await boardCatalogApi.exportCatalogCsv(effectiveBoardId);
      // Open the signed URL in a new tab — browsers handle text/csv as a
      // download, so this triggers the file save without leaving the
      // current view. Some browsers (notably Safari) treat
      // ``window.open`` after an async round-trip as non-user-initiated
      // and return ``null`` (popup blocked). When that happens, surface
      // the URL as a clickable fallback so the user can finish the
      // download with a direct click.
      const opened = window.open(
        resp.download_url,
        '_blank',
        'noopener,noreferrer',
      );
      if (opened === null) {
        setExportFallbackUrl(resp.download_url);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Export failed';
      setExportError(msg);
    } finally {
      setExportInFlight(false);
    }
  };

  // ── Feature-flag OFF / hydrating ────────────────────────────────────
  if (flagLoading) {
    return (
      <div className="board-dashboard-page" data-testid="board-catalog-page">
        <p className="board-dashboard-state-msg">Loading…</p>
      </div>
    );
  }

  if (!cmcpEnabled) {
    return (
      <div className="board-dashboard-page" data-testid="board-catalog-page">
        <div className="board-dashboard-disabled" role="status">
          <h2>Curriculum-mapped content is currently disabled</h2>
          <p>Contact an admin to enable the CB-CMCP-001 feature flag.</p>
        </div>
      </div>
    );
  }

  // ── No board scope ──────────────────────────────────────────────────
  if (!effectiveBoardId) {
    return (
      <div className="board-dashboard-page" data-testid="board-catalog-page">
        <header className="board-dashboard-header">
          <div className="board-dashboard-kicker">
            CB-CMCP-001 / Board admin
          </div>
          <h1 className="board-dashboard-title">Catalog browse</h1>
        </header>
        {userIsAdmin ? (
          <div className="board-dashboard-disabled" role="status">
            <h2>Pick a board to inspect</h2>
            <p>
              Add a <code>?board_id=&lt;board-id&gt;</code> query parameter
              to the URL, or enter one below.
            </p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                setAppliedAdminBoard(adminBoardInput.trim());
              }}
              className="board-dashboard-board-picker"
            >
              <label htmlFor="catalog-board-id-input">
                Board id:
                <input
                  id="catalog-board-id-input"
                  type="text"
                  value={adminBoardInput}
                  onChange={(e) => setAdminBoardInput(e.target.value)}
                  placeholder="e.g. TDSB"
                />
              </label>
              <button type="submit" className="board-dashboard-submit-btn">
                Inspect
              </button>
            </form>
          </div>
        ) : (
          <div className="board-dashboard-disabled" role="status">
            <h2>No board assigned</h2>
            <p>
              Your account is not linked to a board. Contact your
              administrator to be stamped to a board.
            </p>
          </div>
        )}
      </div>
    );
  }

  const hasNext = Boolean(catalogQuery.data?.next_cursor);
  const hasPrev = cursorStack.length > 1;

  return (
    <div className="board-dashboard-page" data-testid="board-catalog-page">
      <header className="board-dashboard-header">
        <div className="board-dashboard-kicker">
          CB-CMCP-001 / Board admin
        </div>
        <h1 className="board-dashboard-title">Catalog browse</h1>
        <p className="board-dashboard-subtitle">
          Browse APPROVED CMCP artifacts for board{' '}
          <strong>{effectiveBoardId}</strong>. Filter by subject / grade /
          content type, sort by any column, or export the full catalog as CSV.
        </p>
        <nav className="board-catalog-nav" aria-label="Board admin views">
          <Link to="/board/dashboard" className="board-catalog-nav-link">
            ← Coverage dashboard
          </Link>
        </nav>
      </header>

      <section className="board-dashboard-section">
        <div className="board-catalog-toolbar">
          <form
            className="board-catalog-filters"
            onSubmit={handleApplyFilters}
            aria-label="Catalog filters"
          >
            <label htmlFor="catalog-subject-input">
              Subject:
              <input
                id="catalog-subject-input"
                type="text"
                value={subjectInput}
                onChange={(e) => setSubjectInput(e.target.value)}
                placeholder="e.g. MATH"
              />
            </label>
            <label htmlFor="catalog-grade-input">
              Grade:
              <input
                id="catalog-grade-input"
                type="number"
                value={gradeInput}
                onChange={(e) => setGradeInput(e.target.value)}
                placeholder="e.g. 5"
                min={1}
                max={12}
              />
            </label>
            <label htmlFor="catalog-content-type-input">
              Type:
              <input
                id="catalog-content-type-input"
                type="text"
                value={contentTypeInput}
                onChange={(e) => setContentTypeInput(e.target.value)}
                placeholder="e.g. STUDY_GUIDE"
              />
            </label>
            <button
              type="submit"
              className="board-dashboard-submit-btn"
              data-testid="apply-filters-btn"
            >
              Apply
            </button>
            <button
              type="button"
              className="board-catalog-secondary-btn"
              onClick={handleClearFilters}
              data-testid="clear-filters-btn"
            >
              Clear
            </button>
          </form>
          <div className="board-catalog-export">
            <button
              type="button"
              className="board-dashboard-submit-btn"
              onClick={handleExport}
              disabled={exportInFlight}
              data-testid="export-csv-btn"
            >
              {exportInFlight ? 'Exporting…' : 'Export CSV'}
            </button>
          </div>
        </div>
        {exportError ? (
          <div
            className="board-dashboard-error"
            role="alert"
            data-testid="export-error"
          >
            <p>Export failed: {exportError}</p>
          </div>
        ) : null}
        {exportFallbackUrl ? (
          <div
            className="board-dashboard-state-msg"
            role="status"
            data-testid="export-fallback"
          >
            <p>
              Your browser blocked the download tab. Use this direct link
              instead:{' '}
              <a
                href={exportFallbackUrl}
                target="_blank"
                rel="noopener noreferrer"
                data-testid="export-fallback-link"
              >
                Download CSV
              </a>
            </p>
          </div>
        ) : null}

        {catalogQuery.isLoading ? (
          <p
            className="board-dashboard-state-msg"
            data-testid="board-catalog-loading"
          >
            Loading catalog…
          </p>
        ) : catalogQuery.isError ? (
          <div
            className="board-dashboard-error"
            role="alert"
            data-testid="board-catalog-error"
          >
            <h3>Couldn’t load catalog</h3>
            <p>
              {catalogQuery.error instanceof Error
                ? catalogQuery.error.message
                : 'Request failed.'}
            </p>
          </div>
        ) : sortedArtifacts.length === 0 ? (
          <p
            className="board-dashboard-state-msg"
            data-testid="board-catalog-empty"
          >
            No artifacts match the current filters.
          </p>
        ) : (
          <table
            className="board-catalog-table"
            data-testid="board-catalog-table"
          >
            <thead>
              <tr>
                {(Object.keys(SORT_LABELS) as SortField[]).map((field) => (
                  <th key={field} scope="col">
                    <button
                      type="button"
                      className="board-catalog-sort-btn"
                      onClick={() => handleSort(field)}
                      data-testid={`sort-${field}`}
                      aria-sort={
                        sortField === field
                          ? sortDir === 'asc'
                            ? 'ascending'
                            : 'descending'
                          : 'none'
                      }
                    >
                      {SORT_LABELS[field]}
                      {sortField === field
                        ? sortDir === 'asc'
                          ? ' ▲'
                          : ' ▼'
                        : ''}
                    </button>
                  </th>
                ))}
                <th scope="col">State</th>
              </tr>
            </thead>
            <tbody>
              {sortedArtifacts.map((art) => (
                <tr key={art.id} data-testid={`catalog-row-${art.id}`}>
                  <td>{art.id}</td>
                  <td>{art.title}</td>
                  <td>{art.content_type}</td>
                  <td>{art.subject_code ?? '—'}</td>
                  <td>{art.grade ?? '—'}</td>
                  <td>
                    {art.created_at
                      ? art.created_at.slice(0, 10)
                      : '—'}
                  </td>
                  <td>{art.state}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <div className="board-catalog-pagination">
          <button
            type="button"
            className="board-catalog-secondary-btn"
            onClick={handlePrevPage}
            disabled={!hasPrev}
            data-testid="prev-page-btn"
          >
            ← Previous
          </button>
          <span className="board-catalog-page-indicator">
            Page {cursorStack.length}
          </span>
          <button
            type="button"
            className="board-catalog-secondary-btn"
            onClick={handleNextPage}
            disabled={!hasNext}
            data-testid="next-page-btn"
          >
            Next →
          </button>
        </div>
      </section>
    </div>
  );
}
