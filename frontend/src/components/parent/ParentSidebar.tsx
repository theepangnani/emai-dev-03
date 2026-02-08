import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { StudyGuide } from '../../api/client';
import { studyApi } from '../../api/client';
import { CourseAssignSelect } from '../CourseAssignSelect';
import type { CalendarAssignment } from '../calendar/types';

interface CourseInfo {
  id: number;
  name: string;
  subject?: string | null;
  teacher_name?: string | null;
}

interface ParentCourse {
  id: number;
  name: string;
  subject: string | null;
}

interface ParentSidebarProps {
  childCourses: CourseInfo[];
  parentCourses: ParentCourse[];
  myStudyGuides: StudyGuide[];
  childStudyGuides: StudyGuide[];
  childName: string;
  undatedAssignments: CalendarAssignment[];
  onAssignCourse: () => void;
  onCreateCourse: () => void;
  onSyncCourses: () => void;
  onDeleteGuide: (id: number) => void;
  onUpdateGuides: (updater: (prev: StudyGuide[]) => StudyGuide[]) => void;
  onAssignmentClick: (assignment: CalendarAssignment) => void;
  syncState: string;
  syncMessage: string;
  googleConnected: boolean;
  hasParentCourses: boolean;
  hasChild: boolean;
}

function SidebarSection({ title, count, defaultOpen = false, children }: { title: string; count?: number; defaultOpen?: boolean; children: React.ReactNode }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="sidebar-section">
      <div className="sidebar-section-header" onClick={() => setOpen(!open)}>
        <span>
          {title}
          {count != null && <span className="sidebar-count">{count}</span>}
        </span>
        <span className="sidebar-chevron">{open ? '\u25B4' : '\u25BE'}</span>
      </div>
      {open && <div className="sidebar-section-body">{children}</div>}
    </div>
  );
}

export function ParentSidebar({
  childCourses, parentCourses, myStudyGuides, childStudyGuides,
  childName, undatedAssignments,
  onAssignCourse, onCreateCourse, onSyncCourses,
  onDeleteGuide, onUpdateGuides, onAssignmentClick,
  syncState, syncMessage, googleConnected,
  hasParentCourses, hasChild,
}: ParentSidebarProps) {
  const navigate = useNavigate();

  return (
    <div className="parent-sidebar">
      {/* Courses */}
      <SidebarSection title="Courses" count={childCourses.length} defaultOpen={true}>
        {hasChild && (
          <div className="sidebar-actions">
            {hasParentCourses && (
              <button className="sidebar-action-btn" onClick={onAssignCourse}>Assign</button>
            )}
            <button className="sidebar-action-btn" onClick={onCreateCourse}>+ New</button>
            {googleConnected && (
              <button
                className="sidebar-action-btn"
                onClick={onSyncCourses}
                disabled={syncState === 'syncing'}
              >
                Sync
              </button>
            )}
          </div>
        )}
        {syncMessage && (
          <div className={`sidebar-sync-msg ${syncState === 'error' ? 'error' : ''}`}>{syncMessage}</div>
        )}
        {childCourses.length > 0 ? (
          <ul className="sidebar-list">
            {childCourses.map(c => (
              <li key={c.id} className="sidebar-list-item">
                <span className="sidebar-item-name">{c.name}</span>
                {c.subject && <span className="sidebar-tag">{c.subject}</span>}
              </li>
            ))}
          </ul>
        ) : (
          <p className="sidebar-empty">No courses yet</p>
        )}
        {parentCourses.length > 0 && (
          <>
            <div className="sidebar-sub-header">My Courses</div>
            <ul className="sidebar-list">
              {parentCourses.map(c => (
                <li key={c.id} className="sidebar-list-item">
                  <span className="sidebar-item-name">{c.name}</span>
                  {c.subject && <span className="sidebar-tag">{c.subject}</span>}
                </li>
              ))}
            </ul>
          </>
        )}
      </SidebarSection>

      {/* Study Materials */}
      <SidebarSection title="Study Materials" count={myStudyGuides.length + childStudyGuides.length}>
        {myStudyGuides.length > 0 ? (
          <ul className="sidebar-list">
            {myStudyGuides.map(guide => (
              <li key={guide.id} className="sidebar-list-item clickable">
                <div
                  className="sidebar-item-name"
                  onClick={() => navigate(
                    guide.guide_type === 'quiz' ? `/study/quiz/${guide.id}`
                      : guide.guide_type === 'flashcards' ? `/study/flashcards/${guide.id}`
                      : `/study/guide/${guide.id}`
                  )}
                >
                  <span className="sidebar-guide-icon">
                    {guide.guide_type === 'quiz' ? '?' : guide.guide_type === 'flashcards' ? '\uD83C\uDCCF' : '\uD83D\uDCD6'}
                  </span>
                  {guide.title}
                </div>
                <div className="sidebar-item-actions">
                  <CourseAssignSelect
                    guideId={guide.id}
                    currentCourseId={guide.course_id}
                    onCourseChanged={(courseId) => onUpdateGuides(prev =>
                      prev.map(g => g.id === guide.id ? { ...g, course_id: courseId } : g)
                    )}
                  />
                  <button
                    className="sidebar-delete-btn"
                    onClick={async () => {
                      await studyApi.deleteGuide(guide.id);
                      onDeleteGuide(guide.id);
                    }}
                  >
                    ✕
                  </button>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="sidebar-empty">No study materials yet</p>
        )}
        {childStudyGuides.length > 0 && (
          <>
            <div className="sidebar-sub-header">{childName}'s Materials</div>
            <ul className="sidebar-list">
              {childStudyGuides.map(guide => (
                <li key={guide.id} className="sidebar-list-item clickable">
                  <span
                    className="sidebar-item-name"
                    onClick={() => navigate(
                      guide.guide_type === 'quiz' ? `/study/quiz/${guide.id}`
                        : guide.guide_type === 'flashcards' ? `/study/flashcards/${guide.id}`
                        : `/study/guide/${guide.id}`
                    )}
                  >
                    <span className="sidebar-guide-icon">
                      {guide.guide_type === 'quiz' ? '?' : guide.guide_type === 'flashcards' ? '\uD83C\uDCCF' : '\uD83D\uDCD6'}
                    </span>
                    {guide.title}
                  </span>
                </li>
              ))}
            </ul>
          </>
        )}
      </SidebarSection>

      {/* Messages */}
      <div className="sidebar-section">
        <div className="sidebar-section-header" onClick={() => navigate('/messages')}>
          <span>Messages</span>
          <span className="sidebar-link-arrow">&rarr;</span>
        </div>
      </div>

      {/* Undated Assignments */}
      {undatedAssignments.length > 0 && (
        <SidebarSection title="Undated" count={undatedAssignments.length}>
          <ul className="sidebar-list">
            {undatedAssignments.map(a => (
              <li key={a.id} className="sidebar-list-item clickable" onClick={() => onAssignmentClick(a)}>
                <span className="cal-entry-dot" style={{ background: a.courseColor }} />
                <span className="sidebar-item-name">{a.title}</span>
              </li>
            ))}
          </ul>
        </SidebarSection>
      )}
    </div>
  );
}
