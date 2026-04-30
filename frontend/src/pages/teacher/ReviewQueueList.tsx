/**
 * CB-CMCP-001 M3-A 3A-2 (#4582) — Teacher review queue: list view.
 *
 * Renders the paginated PENDING_REVIEW table from
 * `GET /api/cmcp/review/queue`. Sort + page controls live here; the
 * parent page owns the selection state.
 */
import type { ReviewQueueItem, ReviewSortField } from '../../api/cmcpReview';

interface ReviewQueueListProps {
  items: ReviewQueueItem[];
  total: number;
  page: number;
  limit: number;
  sortBy: ReviewSortField;
  isLoading: boolean;
  isFetching: boolean;
  error: Error | null;
  selectedId: number | null;
  onSelect: (artifactId: number) => void;
  onSortChange: (sortBy: ReviewSortField) => void;
  onPageChange: (page: number) => void;
}

function formatDate(value: string | null): string {
  if (!value) return '—';
  try {
    const dt = new Date(value);
    if (Number.isNaN(dt.getTime())) return value;
    return dt.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return value;
  }
}

export function ReviewQueueList({
  items,
  total,
  page,
  limit,
  sortBy,
  isLoading,
  isFetching,
  error,
  selectedId,
  onSelect,
  onSortChange,
  onPageChange,
}: ReviewQueueListProps) {
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const startIndex = total === 0 ? 0 : (page - 1) * limit + 1;
  const endIndex = Math.min(page * limit, total);

  return (
    <div className="cmcp-review-list" data-testid="cmcp-review-list">
      <div className="cmcp-review-list-controls" role="region" aria-label="Queue controls">
        <label className="cmcp-review-control-group">
          <span className="cmcp-review-control-label">Sort by</span>
          <select
            className="cmcp-review-control-select"
            value={sortBy}
            onChange={(e) => onSortChange(e.target.value as ReviewSortField)}
            aria-label="Sort review queue"
          >
            <option value="created_at">Newest first</option>
            <option value="content_type">Content type</option>
            <option value="subject">Subject</option>
          </select>
        </label>
        <div className="cmcp-review-control-summary" aria-live="polite">
          {total === 0
            ? 'No items pending review'
            : `Showing ${startIndex}–${endIndex} of ${total}`}
          {isFetching && !isLoading && (
            <span className="cmcp-review-fetching"> · refreshing…</span>
          )}
        </div>
      </div>

      {error && (
        <div className="cmcp-review-error" role="alert">
          {error.message || 'Failed to load review queue.'}
        </div>
      )}

      {isLoading ? (
        <p className="cmcp-review-state-msg">Loading review queue…</p>
      ) : items.length === 0 ? (
        <div className="cmcp-review-state-msg" role="status">
          <h3>No artifacts pending review</h3>
          <p>New CMCP-generated artifacts that need teacher sign-off will appear here.</p>
        </div>
      ) : (
        <div className="cmcp-review-table-wrap">
          <table
            className="cmcp-review-table"
            aria-label="Pending review artifacts"
          >
            <thead>
              <tr>
                <th scope="col">Title</th>
                <th scope="col">Type</th>
                <th scope="col">SE codes</th>
                <th scope="col">Persona</th>
                <th scope="col">Created</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => {
                const isSelected = row.id === selectedId;
                return (
                  <tr
                    key={row.id}
                    data-testid={`cmcp-review-row-${row.id}`}
                    className={
                      isSelected ? 'cmcp-review-row cmcp-review-row--selected' : 'cmcp-review-row'
                    }
                  >
                    <td>
                      <button
                        type="button"
                        className="cmcp-review-row-link"
                        onClick={() => onSelect(row.id)}
                        aria-label={`Open review for ${row.title}`}
                        aria-current={isSelected ? 'true' : undefined}
                      >
                        {row.title}
                      </button>
                    </td>
                    <td>
                      <span className="cmcp-review-type-chip">
                        {row.guide_type}
                      </span>
                    </td>
                    <td className="cmcp-review-se-cell">
                      {row.se_codes.length === 0
                        ? '—'
                        : row.se_codes.slice(0, 3).join(', ') +
                          (row.se_codes.length > 3
                            ? ` +${row.se_codes.length - 3}`
                            : '')}
                    </td>
                    <td>{row.requested_persona ?? '—'}</td>
                    <td>{formatDate(row.created_at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <div className="cmcp-review-pagination" role="navigation" aria-label="Pagination">
          <button
            type="button"
            className="cmcp-review-page-btn"
            onClick={() => onPageChange(Math.max(1, page - 1))}
            disabled={page <= 1}
          >
            Previous
          </button>
          <span className="cmcp-review-page-indicator">
            Page {page} of {totalPages}
          </span>
          <button
            type="button"
            className="cmcp-review-page-btn"
            onClick={() => onPageChange(Math.min(totalPages, page + 1))}
            disabled={page >= totalPages}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
