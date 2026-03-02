import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { courseContentsApi } from '../api/client';
import type { TeacherMaterialItem } from '../api/client';
import { DashboardLayout } from '../components/DashboardLayout';
import { PageNav } from '../components/PageNav';
import { PageSkeleton } from '../components/Skeleton';
import './TeacherMaterialsPage.css';

const MATERIAL_TYPE_TABS = [
  { value: '', label: 'All' },
  { value: 'notes', label: 'Notes' },
  { value: 'test', label: 'Tests' },
  { value: 'lab', label: 'Labs' },
  { value: 'assignment', label: 'Assignments' },
  { value: 'report_card', label: 'Report Cards' },
];

const TYPE_BADGE_CLASS: Record<string, string> = {
  notes: 'tm-badge-notes',
  test: 'tm-badge-test',
  lab: 'tm-badge-lab',
  assignment: 'tm-badge-assignment',
  report_card: 'tm-badge-report-card',
};

const TYPE_LABEL: Record<string, string> = {
  notes: 'Notes',
  test: 'Test',
  lab: 'Lab',
  assignment: 'Assignment',
  report_card: 'Report Card',
};

function formatFileSize(bytes: number | null): string {
  if (!bytes) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

export function TeacherMaterialsPage() {
  const navigate = useNavigate();
  const [materials, setMaterials] = useState<TeacherMaterialItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('');
  const [offset, setOffset] = useState(0);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [error, setError] = useState('');

  const LIMIT = 20;

  const loadMaterials = useCallback(async (tab: string, off: number) => {
    setLoading(true);
    setError('');
    try {
      const params: Record<string, any> = { limit: LIMIT, offset: off };
      if (tab) params.material_type = tab;
      const result = await courseContentsApi.getTeacherMaterials(params);
      setMaterials(result.items);
      setTotal(result.total);
    } catch {
      setError('Failed to load materials. Please try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMaterials(activeTab, offset);
  }, [activeTab, offset, loadMaterials]);

  const handleTabChange = (tab: string) => {
    setActiveTab(tab);
    setOffset(0);
  };

  const handleDelete = async (id: number, title: string) => {
    if (!window.confirm(`Archive "${title}"? It can be restored later from the course detail page.`)) return;
    setDeletingId(id);
    try {
      await courseContentsApi.delete(id);
      await loadMaterials(activeTab, offset);
    } catch {
      setError('Failed to delete material.');
    } finally {
      setDeletingId(null);
    }
  };

  const totalPages = Math.ceil(total / LIMIT);
  const currentPage = Math.floor(offset / LIMIT) + 1;

  return (
    <DashboardLayout welcomeSubtitle="All your uploaded materials">
      <div className="tm-page">
        <PageNav label="Back" />
        <div className="tm-header">
          <h2 className="tm-title">Materials Library</h2>
          <p className="tm-subtitle">All materials you have uploaded across your courses. Filter by type below.</p>
        </div>

        {/* Filter Tabs */}
        <div className="tm-tabs" role="tablist">
          {MATERIAL_TYPE_TABS.map((tab) => (
            <button
              key={tab.value}
              className={`tm-tab${activeTab === tab.value ? ' active' : ''}`}
              onClick={() => handleTabChange(tab.value)}
              role="tab"
              aria-selected={activeTab === tab.value}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {error && <div className="tm-error">{error}</div>}

        {loading ? (
          <PageSkeleton />
        ) : materials.length === 0 ? (
          <div className="tm-empty">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
            </svg>
            <p>No materials found{activeTab ? ` for type "${TYPE_LABEL[activeTab] || activeTab}"` : ''}.</p>
          </div>
        ) : (
          <>
            <div className="tm-count">{total} material{total !== 1 ? 's' : ''}</div>
            <div className="tm-table-wrapper">
              <table className="tm-table">
                <thead>
                  <tr>
                    <th>Material Name</th>
                    <th>Type</th>
                    <th>Course</th>
                    <th>Upload Date</th>
                    <th>Size</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {materials.map((mat) => (
                    <tr key={mat.id}>
                      <td className="tm-cell-name">
                        <span className="tm-material-title">{mat.title}</span>
                        {mat.file_name && mat.file_name !== mat.title && (
                          <span className="tm-material-filename">{mat.file_name}</span>
                        )}
                      </td>
                      <td>
                        <span className={`tm-badge ${TYPE_BADGE_CLASS[mat.material_type] || ''}`}>
                          {TYPE_LABEL[mat.material_type] || mat.material_type}
                        </span>
                      </td>
                      <td className="tm-cell-course">
                        {mat.course_name ? (
                          <button
                            className="tm-course-link"
                            onClick={() => navigate(`/courses/${mat.course_id}`)}
                          >
                            {mat.course_name}
                          </button>
                        ) : '—'}
                      </td>
                      <td className="tm-cell-date">{formatDate(mat.upload_date)}</td>
                      <td className="tm-cell-size">{formatFileSize(mat.file_size_bytes)}</td>
                      <td className="tm-cell-actions">
                        <button
                          className="tm-action-btn tm-action-view"
                          onClick={() => navigate(`/course-materials/${mat.id}`)}
                          title="View"
                        >
                          View
                        </button>
                        <button
                          className="tm-action-btn tm-action-delete"
                          onClick={() => handleDelete(mat.id, mat.title)}
                          disabled={deletingId === mat.id}
                          title="Archive"
                        >
                          {deletingId === mat.id ? '...' : 'Delete'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="tm-pagination">
                <button
                  className="tm-page-btn"
                  disabled={currentPage === 1}
                  onClick={() => setOffset(Math.max(0, offset - LIMIT))}
                >
                  Previous
                </button>
                <span className="tm-page-info">Page {currentPage} of {totalPages}</span>
                <button
                  className="tm-page-btn"
                  disabled={currentPage === totalPages}
                  onClick={() => setOffset(offset + LIMIT)}
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </DashboardLayout>
  );
}
