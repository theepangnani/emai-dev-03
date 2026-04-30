/**
 * CB-CMCP-001 M3-H 3H-1 (#4663) — Board admin dashboard.
 *
 * Route: /board/dashboard
 * RBAC: BOARD_ADMIN + ADMIN (gated by `<ProtectedRoute>` in App.tsx).
 *       Backend `/api/board/{board_id}/catalog` (3E-1, PR #4671) enforces
 *       the same gate independently — the route gate is purely UX.
 *
 * Surface
 * -------
 * Single-pane dashboard rendering a strand × grade coverage heatmap for
 * the caller's board. The board id comes from the authenticated user's
 * profile when present (BOARD_ADMIN); ADMIN callers can supply a
 * `?board_id=…` query param to inspect any board (matches the backend's
 * ADMIN bypass).
 *
 * Data flow
 * ---------
 *   GET /api/board/{board_id}/catalog?limit=200
 *       → { artifacts: BoardCatalogArtifact[], next_cursor }
 *
 * The strand × grade map is derived locally from `artifacts[*].se_codes[0]`
 * — Ontario SE codes are namespaced `<SUBJECT>.<GRADE>.<STRAND>.<...>`.
 * Same parse rule as 3E-2's `coverage_map_service` on the backend; the
 * dedicated REST endpoint for the precomputed map is not in this stripe's
 * scope (3H-1 calls only 3E-1 per the issue spec).
 *
 * Out of scope (per #4663)
 * ------------------------
 * - Catalog browse (3H-2, Wave 3 — will reuse this route + nav).
 * - Pagination beyond the first page (single page is enough to see the
 *   coverage shape; full browse comes in 3H-2).
 * - CSV export (3E-3 ships the signed-url surface separately).
 */
import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';

import { useAuth } from '../../context/AuthContext';
import { useFeatureFlagState } from '../../hooks/useFeatureToggle';
import { boardCatalogApi } from '../../api/boardCatalog';
import { CoverageHeatmap } from '../../components/board/CoverageHeatmap';
import { deriveCoverageMap } from './deriveCoverageMap';

import './BoardDashboardPage.css';

const PAGE_LIMIT = 200;

function userBoardId(user: ReturnType<typeof useAuth>['user']): string | null {
  // The authenticated User profile carries a `board_id` field on
  // BOARD_ADMIN accounts (set by the backend stamping in 0B-* / M2). The
  // shared frontend User type doesn't surface it explicitly, so we read
  // it through a typed helper. Fall through to null when absent.
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

export function BoardDashboardPage() {
  const { user } = useAuth();
  const { enabled: cmcpEnabled, isLoading: flagLoading } =
    useFeatureFlagState('cmcp.enabled');
  const [searchParams] = useSearchParams();
  // Two pieces of state for the admin board picker: `adminBoardInput`
  // tracks what the user is typing (controlled <input>), and
  // `appliedAdminBoard` is the value the query actually fetches against.
  // Decoupling the two prevents per-keystroke API calls — the admin must
  // submit the form (via Enter or the explicit button) before the query
  // fires, so partial values like "T" / "TD" / "TDS" never hit the
  // backend (avoids 404 noise + audit-log pollution).
  const [adminBoardInput, setAdminBoardInput] = useState<string>('');
  const [appliedAdminBoard, setAppliedAdminBoard] = useState<string>('');

  const adminBoardOverride = searchParams.get('board_id');
  const profileBoard = userBoardId(user);
  const userIsAdmin = isAdmin(user);

  // BOARD_ADMIN → must use their stamped board_id (backend would 404 any
  // other value anyway). ADMIN → can override via ?board_id= query param,
  // or via the submitted input below (NOT the in-progress input).
  const adminFallback = userIsAdmin
    ? (adminBoardOverride ?? (appliedAdminBoard.trim() || null))
    : null;
  const effectiveBoardId = profileBoard ?? adminFallback;

  const queryEnabled = cmcpEnabled && Boolean(effectiveBoardId);

  const catalogQuery = useQuery({
    queryKey: ['board-catalog', effectiveBoardId],
    queryFn: () =>
      boardCatalogApi.getCatalog(effectiveBoardId as string, {
        limit: PAGE_LIMIT,
      }),
    enabled: queryEnabled,
  });

  const coverageMap = useMemo(
    () => deriveCoverageMap(catalogQuery.data?.artifacts ?? []),
    [catalogQuery.data?.artifacts],
  );

  // ── Feature-flag OFF / hydrating ────────────────────────────────────
  if (flagLoading) {
    return (
      <div className="board-dashboard-page" data-testid="board-dashboard-page">
        <p className="board-dashboard-state-msg">Loading…</p>
      </div>
    );
  }

  if (!cmcpEnabled) {
    return (
      <div className="board-dashboard-page" data-testid="board-dashboard-page">
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
      <div className="board-dashboard-page" data-testid="board-dashboard-page">
        <header className="board-dashboard-header">
          <div className="board-dashboard-kicker">
            CB-CMCP-001 / Board admin
          </div>
          <h1 className="board-dashboard-title">Coverage dashboard</h1>
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
                // Only commit the value to the query on explicit submit
                // — see comment on `appliedAdminBoard` state. Trimming
                // here so a stray space doesn't make the query fire on
                // an effectively-empty value.
                setAppliedAdminBoard(adminBoardInput.trim());
              }}
              className="board-dashboard-board-picker"
            >
              <label htmlFor="board-id-input">
                Board id:
                <input
                  id="board-id-input"
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

  return (
    <div className="board-dashboard-page" data-testid="board-dashboard-page">
      <header className="board-dashboard-header">
        <div className="board-dashboard-kicker">
          CB-CMCP-001 / Board admin
        </div>
        <h1 className="board-dashboard-title">Coverage dashboard</h1>
        <p className="board-dashboard-subtitle">
          Strand × grade view of APPROVED CMCP artifacts for board{' '}
          <strong>{effectiveBoardId}</strong>. Cells coloured by artifact
          count: <span className="board-dashboard-pill-empty">0</span>{' '}
          <span className="board-dashboard-pill-sparse">1–3</span>{' '}
          <span className="board-dashboard-pill-covered">4+</span>.
        </p>
      </header>

      <section className="board-dashboard-section">
        {catalogQuery.isLoading ? (
          <p
            className="board-dashboard-state-msg"
            data-testid="board-dashboard-loading"
          >
            Loading coverage…
          </p>
        ) : catalogQuery.isError ? (
          <div
            className="board-dashboard-error"
            role="alert"
            data-testid="board-dashboard-error"
          >
            <h3>Couldn’t load coverage</h3>
            <p>
              {catalogQuery.error instanceof Error
                ? catalogQuery.error.message
                : 'Request failed.'}
            </p>
          </div>
        ) : (
          <CoverageHeatmap coverageMap={coverageMap} />
        )}
      </section>
    </div>
  );
}
