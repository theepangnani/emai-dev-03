import { useState, useEffect, Suspense } from 'react';
import { Link } from 'react-router-dom';
import { parentApi, type BriefingNote } from '../api/client';
import { DashboardLayout } from '../components/DashboardLayout';
import { ContentCard, MarkdownBody, MarkdownErrorBoundary } from '../components/ContentCard';
import { useConfirm } from '../components/ConfirmModal';
import { PageNav } from '../components/PageNav';
import './ParentBriefingNotesPage.css';

export function ParentBriefingNotesPage() {
  const [notes, setNotes] = useState<BriefingNote[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const { confirm, confirmModal } = useConfirm();

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 4000);
  };

  useEffect(() => {
    parentApi.listBriefingNotes()
      .then(setNotes)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleDelete = async (note: BriefingNote) => {
    const ok = await confirm({
      title: 'Delete Parent Briefing',
      message: `Delete "${note.title}"?`,
      confirmLabel: 'Delete',
    });
    if (!ok) return;
    try {
      await parentApi.deleteBriefingNote(note.id);
      setNotes(prev => prev.filter(n => n.id !== note.id));
      showToast('Briefing note deleted');
    } catch {
      showToast('Failed to delete briefing note');
    }
  };

  return (
    <DashboardLayout showBackButton headerSlot={() => null}>
      <div className="briefing-notes-page">
        <PageNav items={[
          { label: 'Home', to: '/dashboard' },
          { label: 'Parent Briefing Notes' },
        ]} />

        <div className="briefing-notes-header">
          <h2>Parent Briefing Notes</h2>
          <p className="briefing-notes-subtitle">
            AI-generated summaries to help you understand what your child is learning.
          </p>
        </div>

        {loading ? (
          <div className="briefing-notes-loading">Loading...</div>
        ) : notes.length === 0 ? (
          <div className="briefing-notes-empty">
            <h3>No briefing notes yet</h3>
            <p>
              Visit any class material and click the &quot;Parent Briefing&quot; tab to generate
              a summary written just for you.
            </p>
            <Link to="/course-materials" className="briefing-notes-link">
              Browse Class Materials
            </Link>
          </div>
        ) : (
          <div className="briefing-notes-list">
            {notes.map(note => (
              <div key={note.id} className="briefing-note-card">
                <div
                  className="briefing-note-header"
                  onClick={() => setExpandedId(expandedId === note.id ? null : note.id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => { if (e.key === 'Enter') setExpandedId(expandedId === note.id ? null : note.id); }}
                >
                  <div className="briefing-note-info">
                    <h3>{note.title}</h3>
                    <div className="briefing-note-meta">
                      {note.course_name && <span className="briefing-note-course">{note.course_name}</span>}
                      {note.student_name && <span className="briefing-note-student">{note.student_name}</span>}
                      <span className="briefing-note-date">
                        {new Date(note.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                      </span>
                    </div>
                  </div>
                  <div className="briefing-note-actions">
                    {note.course_content_id && (
                      <Link
                        to={`/course-materials/${note.course_content_id}?tab=briefing`}
                        className="briefing-note-view-btn"
                        onClick={(e) => e.stopPropagation()}
                      >
                        View Material
                      </Link>
                    )}
                    <button
                      className="briefing-note-delete-btn"
                      onClick={(e) => { e.stopPropagation(); handleDelete(note); }}
                    >
                      Delete
                    </button>
                    <span className={`briefing-note-chevron${expandedId === note.id ? ' expanded' : ''}`}>
                      &#9660;
                    </span>
                  </div>
                </div>
                {expandedId === note.id && (
                  <div className="briefing-note-body">
                    <ContentCard>
                      <MarkdownErrorBoundary>
                        <Suspense fallback={<div>Rendering...</div>}>
                          <MarkdownBody content={note.content} />
                        </Suspense>
                      </MarkdownErrorBoundary>
                    </ContentCard>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
      {confirmModal}
      {toast && <div className="toast-notification">{toast}</div>}
    </DashboardLayout>
  );
}
