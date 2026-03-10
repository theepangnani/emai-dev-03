import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { coursesApi, courseContentsApi, studyApi, assignmentsApi } from '../api/client';
import type { CourseContentItem, AssignmentItem, SubmissionResponse, SubmissionListItem } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { DashboardLayout } from '../components/DashboardLayout';
import { CreateTaskModal } from '../components/CreateTaskModal';
import { useConfirm } from '../components/ConfirmModal';
import { useFocusTrap } from '../hooks/useFocusTrap';
import { PageSkeleton, ListSkeleton } from '../components/Skeleton';
import { PageNav } from '../components/PageNav';
import { EditMaterialModal } from '../components/EditMaterialModal';
import { AssignmentSubmission } from '../components/AssignmentSubmission';
import { useAIUsage } from '../hooks/useAIUsage';
import { AILimitRequestModal } from '../components/AILimitRequestModal';
import '../components/AssignmentSubmission.css';
import './CourseDetailPage.css';

const CONTENT_TYPES = [
  { value: 'notes', label: 'Notes' },
  { value: 'syllabus', label: 'Syllabus' },
  { value: 'labs', label: 'Labs' },
  { value: 'assignments', label: 'Assignments' },
  { value: 'readings', label: 'Readings' },
  { value: 'resources', label: 'Resources' },
  { value: 'other', label: 'Other' },
];

const MAX_FILE_SIZE_MB = 100;

interface CourseDetail {
  id: number;
  name: string;
  description: string | null;
  subject: string | null;
  teacher_id: number | null;
  teacher_name: string | null;
  teacher_email: string | null;
  created_by_user_id: number | null;
  is_private: boolean;
  require_approval: boolean;
  created_at: string;
  google_classroom_id: string | null;
  classroom_type: string | null;
  class_code: string | null;
}

interface RosterStudent {
  student_id: number;
  user_id: number;
  full_name: string;
  email: string;
  grade_level: number | null;
}

export function CourseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const courseId = Number(id);
  const navigate = useNavigate();
  const { user } = useAuth();

  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [contents, setContents] = useState<CourseContentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [contentsLoading, setContentsLoading] = useState(false);

  // Student roster
  const [students, setStudents] = useState<RosterStudent[]>([]);
  const [showAddStudentModal, setShowAddStudentModal] = useState(false);
  const [addStudentEmail, setAddStudentEmail] = useState('');
  const [addStudentMessage, setAddStudentMessage] = useState('');
  const [addStudentLoading, setAddStudentLoading] = useState(false);
  const [addStudentError, setAddStudentError] = useState('');
  const [addStudentSuccess, setAddStudentSuccess] = useState('');

  // Enrollment requests
  const [enrollmentRequests, setEnrollmentRequests] = useState<Array<{ id: number; course_id: number; student_id: number; student_name: string | null; student_email: string | null; status: string; created_at: string }>>([]);
  const [enrollReqExpanded, setEnrollReqExpanded] = useState(true);
  const [resolvingReqId, setResolvingReqId] = useState<number | null>(null);

  // Assignments
  const [assignments, setAssignments] = useState<AssignmentItem[]>([]);
  const [showAssignmentModal, setShowAssignmentModal] = useState(false);
  const [editingAssignment, setEditingAssignment] = useState<AssignmentItem | null>(null);
  const [assignTitle, setAssignTitle] = useState('');
  const [assignDesc, setAssignDesc] = useState('');
  const [assignDueDate, setAssignDueDate] = useState('');
  const [assignMaxPoints, setAssignMaxPoints] = useState('');
  const [assignSaving, setAssignSaving] = useState(false);
  const [assignError, setAssignError] = useState('');

  // Submission state (#839)
  const [submissionMap, setSubmissionMap] = useState<Record<number, SubmissionResponse>>({});
  const [submissionListMap, setSubmissionListMap] = useState<Record<number, SubmissionListItem[]>>({});
  const [submittingAssignmentId, setSubmittingAssignmentId] = useState<number | null>(null);
  const [expandedSubmissionsId, setExpandedSubmissionsId] = useState<number | null>(null);

  // Edit course modal
  const [showEditModal, setShowEditModal] = useState(false);
  const [editName, setEditName] = useState('');
  const [editSubject, setEditSubject] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editTeacherEmail, setEditTeacherEmail] = useState('');
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState('');

  // Add/Edit content modal
  const [showContentModal, setShowContentModal] = useState(false);
  const [editingContent, setEditingContent] = useState<CourseContentItem | null>(null);
  const [contentTitle, setContentTitle] = useState('');
  const [contentDescription, setContentDescription] = useState('');
  const [contentType, setContentType] = useState('notes');
  const [referenceUrl, setReferenceUrl] = useState('');
  const [googleClassroomUrl, setGoogleClassroomUrl] = useState('');
  const [contentSaving, setContentSaving] = useState(false);
  const [contentError, setContentError] = useState('');

  // Upload document modal
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadTitle, setUploadTitle] = useState('');
  const [uploadType, setUploadType] = useState('notes');
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [extractedText, setExtractedText] = useState('');
  const [extracting, setExtracting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // AI usage
  const { remaining, atLimit, invalidate: refreshAIUsage } = useAIUsage();
  const [showLimitModal, setShowLimitModal] = useState(false);

  // Generate study guide state
  const [generatingContentId, setGeneratingContentId] = useState<number | null>(null);

  // Upload: AI tool selection (#552)
  const [uploadAiTool, setUploadAiTool] = useState<'none' | 'study_guide' | 'quiz' | 'flashcards'>('none');
  const [uploadAiCustomPrompt, setUploadAiCustomPrompt] = useState('');

  // Collapsible sections
  const [materialsExpanded, setMaterialsExpanded] = useState(true);
  const [assignmentsExpanded, setAssignmentsExpanded] = useState(true);
  const [rosterExpanded, setRosterExpanded] = useState(true);

  // Focus traps for modals
  const addStudentModalRef = useFocusTrap<HTMLDivElement>(showAddStudentModal, () => setShowAddStudentModal(false));
  const editCourseModalRef = useFocusTrap<HTMLDivElement>(showEditModal, () => setShowEditModal(false));
  const contentModalRef = useFocusTrap<HTMLDivElement>(showContentModal);
  const uploadModalRef = useFocusTrap<HTMLDivElement>(showUploadModal, () => setShowUploadModal(false));
  const assignmentModalRef = useFocusTrap<HTMLDivElement>(showAssignmentModal, () => setShowAssignmentModal(false));

  // Create task modal context
  const [taskModalContext, setTaskModalContext] = useState<{
    courseId?: number;
    courseContentId?: number;
    title: string;
    label: string;
  } | null>(null);

  // Guard refs to prevent double-submission
  const uploadingRef = useRef(false);
  const generatingRef = useRef(false);

  const { confirm, confirmModal } = useConfirm();

  useEffect(() => {
    if (courseId) loadCourse();
  }, [courseId]);

  const loadCourse = async () => {
    setLoading(true);
    try {
      const courseData = await coursesApi.get(courseId);
      setCourse(courseData);
      try {
        const contentsData = await courseContentsApi.list(courseId);
        setContents(contentsData);
      } catch {
        setContents([]);
      }
      let loadedAssignments: AssignmentItem[] = [];
      try {
        loadedAssignments = await assignmentsApi.list(courseId);
        setAssignments(loadedAssignments);
      } catch {
        setAssignments([]);
      }
      // Load submissions for student users (#839)
      if (user?.role === 'student' && loadedAssignments.length > 0) {
        const subs: Record<number, SubmissionResponse> = {};
        for (const a of loadedAssignments) {
          try {
            const sub = await assignmentsApi.getSubmission(a.id);
            subs[a.id] = sub;
          } catch { /* no submission yet */ }
        }
        setSubmissionMap(subs);
      }
      try {
        const roster = await coursesApi.listStudents(courseId);
        setStudents(roster);
      } catch {
        setStudents([]);
      }
      // Load enrollment requests if course requires approval
      if (courseData.require_approval) {
        try {
          const reqs = await coursesApi.listEnrollmentRequests(courseId);
          setEnrollmentRequests(reqs);
        } catch { /* ignore */ }
      }
    } catch {
      setCourse(null);
    } finally {
      setLoading(false);
    }
  };

  const loadContents = async () => {
    setContentsLoading(true);
    try {
      const data = await courseContentsApi.list(courseId);
      setContents(data);
    } catch { /* ignore */ } finally {
      setContentsLoading(false);
    }
  };

  const isCreator = course?.created_by_user_id === user?.id;
  const isAdmin = user?.role === 'admin';
  const isTeacher = user?.role === 'teacher';
  const canEdit = isCreator || isAdmin;
  const canManageRoster = isCreator || isAdmin || isTeacher;

  const handleAddStudent = async () => {
    if (!addStudentEmail.trim()) return;
    setAddStudentLoading(true);
    setAddStudentError('');
    setAddStudentSuccess('');
    try {
      const result = await coursesApi.addStudent(courseId, addStudentEmail.trim());
      if (result.invited) {
        setAddStudentSuccess(result.message);
      } else {
        setStudents(prev => [...prev, result]);
        setAddStudentSuccess(`${result.full_name} has been added to the class.`);
      }
      setAddStudentEmail('');
    } catch (err: any) {
      setAddStudentError(err.response?.data?.detail || 'Failed to add student');
    } finally {
      setAddStudentLoading(false);
    }
  };

  const handleRemoveStudent = async (studentId: number, name: string) => {
    const ok = await confirm({ title: 'Remove Student', message: `Remove ${name} from this class?`, variant: 'danger' });
    if (!ok) return;
    try {
      await coursesApi.removeStudent(courseId, studentId);
      setStudents(prev => prev.filter(s => s.student_id !== studentId));
    } catch { /* ignore */ }
  };

  const handleResolveEnrollmentRequest = async (requestId: number, status: 'approved' | 'rejected') => {
    setResolvingReqId(requestId);
    try {
      await coursesApi.resolveEnrollmentRequest(courseId, requestId, status);
      setEnrollmentRequests(prev => prev.filter(r => r.id !== requestId));
      if (status === 'approved') {
        // Reload roster
        try {
          const roster = await coursesApi.listStudents(courseId);
          setStudents(roster);
        } catch { /* ignore */ }
      }
    } catch { /* ignore */ }
    setResolvingReqId(null);
  };

  // Edit course handlers
  const openEditModal = () => {
    if (!course) return;
    setEditName(course.name);
    setEditSubject(course.subject || '');
    setEditDescription(course.description || '');
    setEditTeacherEmail(course.teacher_email || '');
    setEditError('');
    setShowEditModal(true);
  };

  const handleEditCourse = async () => {
    if (!editName.trim()) return;
    setEditSaving(true);
    setEditError('');
    try {
      const updated = await coursesApi.update(courseId, {
        name: editName.trim(),
        subject: editSubject.trim() || undefined,
        description: editDescription.trim() || undefined,
        teacher_email: editTeacherEmail.trim() !== (course?.teacher_email || '') ? editTeacherEmail.trim() : undefined,
      });
      setCourse(updated);
      setShowEditModal(false);
    } catch (err: any) {
      setEditError(err.response?.data?.detail || 'Failed to update course');
    } finally {
      setEditSaving(false);
    }
  };

  const handleDeleteCourse = async () => {
    const ok = await confirm({
      title: 'Delete Class',
      message: `Permanently delete "${course?.name}"? All class materials, assignments, and enrollments will be removed. This cannot be undone.`,
      variant: 'danger',
      confirmLabel: 'Delete Class',
    });
    if (!ok) return;
    try {
      await coursesApi.delete(courseId);
      navigate('/courses');
    } catch (err: any) {
      setEditError(err.response?.data?.detail || 'Failed to delete course');
    }
  };

  // Content CRUD handlers
  const openAddContentModal = () => {
    setEditingContent(null);
    setContentTitle('');
    setContentDescription('');
    setContentType('notes');
    setReferenceUrl('');
    setGoogleClassroomUrl('');
    setContentError('');
    setShowContentModal(true);
  };

  const openEditContentModal = (item: CourseContentItem) => {
    setEditingContent(item);
  };

  const closeContentModal = () => {
    setShowContentModal(false);
    setEditingContent(null);
    setContentTitle('');
    setContentDescription('');
    setContentType('notes');
    setReferenceUrl('');
    setGoogleClassroomUrl('');
    setContentError('');
  };

  const handleSaveContent = async () => {
    if (!contentTitle.trim()) return;
    setContentSaving(true);
    setContentError('');
    try {
      if (editingContent) {
        await courseContentsApi.update(editingContent.id, {
          title: contentTitle.trim(),
          description: contentDescription.trim() || undefined,
          content_type: contentType,
          reference_url: referenceUrl.trim() || undefined,
          google_classroom_url: googleClassroomUrl.trim() || undefined,
        });
      } else {
        await courseContentsApi.create({
          course_id: courseId,
          title: contentTitle.trim(),
          description: contentDescription.trim() || undefined,
          content_type: contentType,
          reference_url: referenceUrl.trim() || undefined,
          google_classroom_url: googleClassroomUrl.trim() || undefined,
        });
      }
      closeContentModal();
      loadContents();
    } catch (err: any) {
      setContentError(err.response?.data?.detail || 'Failed to save content');
    } finally {
      setContentSaving(false);
    }
  };

  const handleDeleteContent = async (contentId: number) => {
    const ok = await confirm({
      title: 'Archive Content',
      message: 'This will archive the content item. You can restore it later from Class Materials.',
      confirmLabel: 'Archive',
    });
    if (!ok) return;
    try {
      await courseContentsApi.delete(contentId);
      loadContents();
    } catch { /* ignore */ }
  };

  // Upload document handlers
  const openUploadModal = () => {
    setSelectedFile(null);
    setUploadTitle('');
    setUploadType('notes');
    setUploadError('');
    setExtractedText('');
    setExtracting(false);
    setIsDragging(false);
    setUploadAiTool('none');
    setUploadAiCustomPrompt('');
    setShowUploadModal(true);
  };

  const handleFileSelect = (file: File) => {
    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      setUploadError(`File size exceeds ${MAX_FILE_SIZE_MB} MB limit`);
      return;
    }
    setSelectedFile(file);
    setUploadError('');
    if (!uploadTitle) setUploadTitle(file.name.replace(/\.[^/.]+$/, ''));

    // Extract text from file
    setExtracting(true);
    studyApi.extractTextFromFile(file)
      .then(result => {
        setExtractedText(result.text);
        setExtracting(false);
      })
      .catch(() => {
        setUploadError('Failed to extract text from file');
        setExtracting(false);
      });
  };

  const handleDragOver = (e: React.DragEvent) => { e.preventDefault(); setIsDragging(true); };
  const handleDragLeave = (e: React.DragEvent) => { e.preventDefault(); setIsDragging(false); };
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelect(file);
  };

  const handleUploadDocument = async () => {
    if (!selectedFile || !uploadTitle.trim()) return;
    if (uploadingRef.current) return;
    uploadingRef.current = true;
    setUploading(true);
    setUploadError('');
    try {
      // Pass ai_tool and ai_custom_prompt to backend; AI generation happens
      // as a background task so the upload returns immediately (#552)
      await courseContentsApi.create({
        course_id: courseId,
        title: uploadTitle.trim(),
        description: `Uploaded from: ${selectedFile.name}`,
        text_content: extractedText || undefined,
        content_type: uploadType,
        ai_tool: uploadAiTool !== 'none' ? uploadAiTool : undefined,
        ai_custom_prompt: uploadAiTool !== 'none' && uploadAiCustomPrompt.trim() ? uploadAiCustomPrompt.trim() : undefined,
      });
      setShowUploadModal(false);
      await loadContents();
    } catch (err: any) {
      setUploadError(err.response?.data?.detail || 'Failed to upload document');
    } finally {
      setUploading(false);
      uploadingRef.current = false;
    }
  };

  // Generate study guide from content item
  const handleGenerateStudyGuide = async (item: CourseContentItem) => {
    const sourceText = item.text_content || item.description;
    if (!sourceText) {
      alert('No content available to generate a study guide from. Add a description or upload a document first.');
      return;
    }
    if (generatingRef.current) return;
    if (atLimit) {
      setShowLimitModal(true);
      return;
    }

    // Check for existing study guide
    try {
      const dupResult = await studyApi.checkDuplicate({ title: item.title, guide_type: 'study_guide' });
      if (dupResult.exists && dupResult.existing_guide) {
        const existing = dupResult.existing_guide;
        const goToExisting = await confirm({
          title: 'Study Guide Exists',
          message: `A study guide already exists: "${existing.title}" (v${existing.version}). Would you like to view it?`,
          confirmLabel: 'View Existing',
          cancelLabel: 'Stay Here',
        });
        if (goToExisting) navigate(`/study/guide/${existing.id}`);
        return;
      }
    } catch { /* continue */ }

    const ok = await confirm({
      title: 'Generate Study Guide',
      message: `Generate a study guide from "${item.title}"? This will use 1 AI credit. You have ${remaining} remaining.`,
      confirmLabel: 'Generate',
      ...(remaining <= 0 ? {
        disableConfirm: true,
        extraActionLabel: 'Request More Credits',
        onExtraAction: () => setShowLimitModal(true),
      } : {}),
    });
    if (!ok) return;

    generatingRef.current = true;
    setGeneratingContentId(item.id);
    try {
      const result = await studyApi.generateGuide({
        content: sourceText,
        title: item.title,
        course_id: courseId,
      });
      refreshAIUsage();
      navigate(`/study/guide/${result.id}`);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to generate study guide');
    } finally {
      setGeneratingContentId(null);
      generatingRef.current = false;
    }
  };

  // Assignment handlers
  const openAddAssignment = () => {
    setEditingAssignment(null);
    setAssignTitle('');
    setAssignDesc('');
    setAssignDueDate('');
    setAssignMaxPoints('');
    setAssignError('');
    setShowAssignmentModal(true);
  };

  const openEditAssignment = (a: AssignmentItem) => {
    setEditingAssignment(a);
    setAssignTitle(a.title);
    setAssignDesc(a.description || '');
    setAssignDueDate(a.due_date ? a.due_date.slice(0, 16) : '');
    setAssignMaxPoints(a.max_points != null ? String(a.max_points) : '');
    setAssignError('');
    setShowAssignmentModal(true);
  };

  const handleSaveAssignment = async () => {
    if (!assignTitle.trim()) return;
    setAssignSaving(true);
    setAssignError('');
    try {
      if (editingAssignment) {
        const updated = await assignmentsApi.update(editingAssignment.id, {
          title: assignTitle.trim(),
          description: assignDesc.trim() || undefined,
          due_date: assignDueDate || null,
          max_points: assignMaxPoints ? Number(assignMaxPoints) : null,
        });
        setAssignments(prev => prev.map(a => a.id === updated.id ? updated : a));
      } else {
        const created = await assignmentsApi.create({
          course_id: courseId,
          title: assignTitle.trim(),
          description: assignDesc.trim() || undefined,
          due_date: assignDueDate || undefined,
          max_points: assignMaxPoints ? Number(assignMaxPoints) : undefined,
        });
        setAssignments(prev => [...prev, created]);
      }
      setShowAssignmentModal(false);
    } catch (err: any) {
      setAssignError(err.response?.data?.detail || 'Failed to save assignment');
    } finally {
      setAssignSaving(false);
    }
  };

  const handleDeleteAssignment = async (a: AssignmentItem) => {
    const ok = await confirm({ title: 'Delete Assignment', message: `Delete "${a.title}"? This cannot be undone.`, variant: 'danger' });
    if (!ok) return;
    try {
      await assignmentsApi.delete(a.id);
      setAssignments(prev => prev.filter(x => x.id !== a.id));
    } catch { /* ignore */ }
  };

  if (loading) {
    return (
      <DashboardLayout welcomeSubtitle="Class details">
        <PageSkeleton />
      </DashboardLayout>
    );
  }

  if (!course) {
    return (
      <DashboardLayout welcomeSubtitle="Class not found">
        <div className="course-detail-empty">
          <p>Class not found or you don't have access.</p>
          <button className="courses-btn secondary btn-secondary btn-sm" onClick={() => navigate('/courses')}>Back to Classes</button>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout welcomeSubtitle={course.name}>
      <div className="course-detail-page">
        <PageNav items={[
          { label: 'Home', to: '/dashboard' },
          { label: 'Classes', to: '/courses' },
          { label: course?.name || 'Class' },
        ]} />

        {/* Course header */}
        <div className="course-detail-header">
          <div className="course-detail-info">
            <h2>{course.name}</h2>
            <div className="course-detail-meta">
              {course.subject && <span className="course-detail-subject">{course.subject}</span>}
              {course.google_classroom_id && <span className="course-detail-badge google">Google Classroom</span>}
              {course.classroom_type === 'school' && <span className="course-detail-badge school">School</span>}
              {course.classroom_type === 'private' && course.google_classroom_id && <span className="course-detail-badge private-gc">Private</span>}
              {course.is_private && <span className="course-detail-badge private">Private</span>}
            </div>
            {course.class_code && (
              <div className="course-detail-class-code">
                <span className="class-code-label">Class Code:</span>
                <code className="class-code-value">{course.class_code}</code>
                <button
                  className="class-code-copy-btn"
                  title="Copy class code"
                  onClick={() => {
                    navigator.clipboard.writeText(course.class_code!);
                    const btn = document.querySelector('.class-code-copy-btn');
                    if (btn) {
                      btn.textContent = 'Copied!';
                      setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
                    }
                  }}
                >Copy</button>
              </div>
            )}
            {course.description && <p className="course-detail-desc">{course.description}</p>}
            {course.teacher_name && (
              <span className="course-detail-teacher">
                Teacher: {course.teacher_name}{course.teacher_email ? ` (${course.teacher_email})` : ''}
              </span>
            )}
            <span className="course-detail-date">
              Created {new Date(course.created_at).toLocaleDateString()}
            </span>
            {course.classroom_type === 'school' && (
              <div className="dtap-disclaimer">
                Document downloads are restricted for school courses. DTAP approval is required for school board connections.
              </div>
            )}
          </div>
          {canEdit && (
            <button className="courses-btn secondary btn-secondary btn-sm" onClick={openEditModal}>&#9998; Edit</button>
          )}
        </div>

      {/* Class Materials Panel */}
      <div className="course-section-panel">
        <div className="course-section-header">
          <button className="collapse-toggle" onClick={() => setMaterialsExpanded(v => !v)}>
            <span className={`section-chevron${materialsExpanded ? ' expanded' : ''}`}>&#9654;</span>
            <h3>Class Materials ({contents.length})</h3>
          </button>
          {canEdit && (
            <div className="course-detail-action-btns">
              <button className="courses-btn secondary btn-secondary btn-sm action-icon-btn" onClick={openAddContentModal}>
                <span className="action-icon">&#128221;</span> Add Class Details
              </button>
              <button className="courses-btn secondary btn-secondary btn-sm action-icon-btn" onClick={openUploadModal}>
                <span className="action-icon">&#128228;</span> Upload Class Material
              </button>
              <button className="courses-btn secondary btn-secondary btn-sm action-icon-btn" onClick={() => setTaskModalContext({
                courseId: courseId,
                title: `Task for ${course.name}`,
                label: `Class: ${course.name}`,
              })}>
                <span className="action-icon">&#9745;</span> Add to Task
              </button>
            </div>
          )}
        </div>
        {materialsExpanded && (
          <>
            {contentsLoading ? (
              <ListSkeleton rows={3} />
            ) : contents.length === 0 ? (
              <div className="course-detail-empty-content">
                <p>{canEdit ? 'No class materials yet. Add notes, links, resources, or upload documents.' : 'No class materials available yet.'}</p>
              </div>
            ) : (
              <div className="course-detail-content-list">
                {contents.map((item) => (
                  <div key={item.id} className="cd-content-item">
                    <div className="cd-content-item-info" onClick={() => navigate(`/course-materials/${item.id}`)} role="button" tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && navigate(`/course-materials/${item.id}`)}>
                      <div className="cd-content-item-top">
                        <span className={`content-type-badge ${item.content_type}`}>
                          {CONTENT_TYPES.find(t => t.value === item.content_type)?.label || item.content_type}
                        </span>
                        {item.google_classroom_material_id && (
                          <span className="course-detail-badge google">Google Classroom</span>
                        )}
                        <span className="cd-content-item-title">{item.title}</span>
                      </div>
                      {item.description && <p className="cd-content-item-desc">{item.description}</p>}
                      {item.text_content && (
                        <p className="cd-content-item-text-preview">
                          {item.text_content.substring(0, 200)}{item.text_content.length > 200 ? '...' : ''}
                        </p>
                      )}
                      <div className="cd-content-item-links">
                        {item.reference_url && (
                          <a href={item.reference_url} target="_blank" rel="noopener noreferrer" className="content-link">
                            Reference Link
                          </a>
                        )}
                        {item.google_classroom_url && (
                          <a href={item.google_classroom_url} target="_blank" rel="noopener noreferrer" className="content-link google">
                            Google Classroom
                          </a>
                        )}
                      </div>
                    </div>
                    <div className="cd-content-item-actions">
                      <button
                        className="content-icon-btn"
                        title={generatingContentId === item.id ? 'Generating...' : 'Generate Study Guide'}
                        aria-label="Generate Study Guide"
                        onClick={() => handleGenerateStudyGuide(item)}
                        disabled={generatingContentId === item.id}
                      >
                        {generatingContentId === item.id ? '\u23F3' : '\uD83D\uDCD6'}
                      </button>
                      <button
                        className="content-icon-btn"
                        title="Create task"
                        aria-label="Create task from this content"
                        onClick={() => setTaskModalContext({
                          courseId: courseId,
                          courseContentId: item.id,
                          title: `Review: ${item.title}`,
                          label: `${item.title} (${course.name})`,
                        })}
                      >
                        &#128203;
                      </button>
                      {item.created_by_user_id === user?.id && (
                        <>
                          <button className="content-icon-btn" title="Edit" aria-label="Edit this content" onClick={() => openEditContentModal(item)}>&#9998;</button>
                          <button className="content-icon-btn danger" title="Archive" aria-label="Archive this content" onClick={() => handleDeleteContent(item.id)}>&#128465;</button>
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>

      {/* Assignments */}
      <div className="course-section-panel">
        <div className="course-section-header">
          <button className="collapse-toggle" onClick={() => setAssignmentsExpanded(v => !v)}>
            <span className={`section-chevron${assignmentsExpanded ? ' expanded' : ''}`}>&#9654;</span>
            <h3>Assignments ({assignments.length})</h3>
          </button>
          {canManageRoster && (
            <button className="courses-btn secondary btn-secondary btn-sm action-icon-btn" onClick={openAddAssignment}>
              <span className="action-icon">+</span> Add Assignment
            </button>
          )}
        </div>
        {assignmentsExpanded && (
          <>
            {assignments.length === 0 ? (
              <p className="course-roster-empty">No assignments yet.</p>
            ) : (
              <div className="course-assignments-list">
                {assignments.map(a => {
                  const sub = submissionMap[a.id];
                  const isStudent = user?.role === 'student';
                  return (
                    <div key={a.id}>
                      <div className="course-assignment-row">
                        <div className="course-assignment-info">
                          <span className="course-assignment-title">{a.title}</span>
                          {a.description && <span className="course-assignment-desc">{a.description}</span>}
                        </div>
                        <div className="course-assignment-meta">
                          {a.due_date && (
                            <span className={`course-assignment-due${new Date(a.due_date) < new Date() ? ' overdue' : ''}`}>
                              Due {new Date(a.due_date).toLocaleDateString()}
                            </span>
                          )}
                          {a.max_points != null && <span className="course-assignment-points">{a.max_points} pts</span>}
                          {a.google_classroom_id && <span className="course-detail-badge google">GC</span>}
                          {/* Student submission status badge (#839) */}
                          {isStudent && sub && sub.status === 'graded' && (
                            <span className="submission-badge graded">Graded: {sub.grade ?? '—'}</span>
                          )}
                          {isStudent && sub && sub.status === 'submitted' && (
                            <span className={`submission-badge submitted${sub.is_late ? ' late' : ''}`}>
                              Submitted{sub.is_late ? ' (Late)' : ''}
                            </span>
                          )}
                          {isStudent && (!sub || sub.status === 'pending') && (
                            <span className="submission-badge not-submitted">Not Submitted</span>
                          )}
                        </div>
                        {/* Student submit button (#839) */}
                        {isStudent && (
                          <div className="course-assignment-actions">
                            <button
                              className="courses-btn secondary btn-secondary btn-sm"
                              style={{ fontSize: '12px', padding: '4px 10px' }}
                              onClick={() => setSubmittingAssignmentId(submittingAssignmentId === a.id ? null : a.id)}
                            >
                              {sub && (sub.status === 'submitted' || sub.status === 'graded') ? 'Resubmit' : 'Submit'}
                            </button>
                          </div>
                        )}
                        {/* Teacher view: show submissions count (#839) */}
                        {canManageRoster && !isStudent && (
                          <div className="course-assignment-actions">
                            <button
                              className="courses-btn secondary btn-secondary btn-sm"
                              style={{ fontSize: '12px', padding: '4px 10px' }}
                              onClick={() => {
                                if (expandedSubmissionsId === a.id) {
                                  setExpandedSubmissionsId(null);
                                } else {
                                  setExpandedSubmissionsId(a.id);
                                  // Load submissions for this assignment
                                  assignmentsApi.listSubmissions(a.id).then(subs => {
                                    setSubmissionListMap(prev => ({ ...prev, [a.id]: subs }));
                                  }).catch(() => {});
                                }
                              }}
                            >
                              Submissions
                            </button>
                            {!a.google_classroom_id && (
                              <>
                                <button className="content-icon-btn" title="Edit" aria-label="Edit assignment" onClick={() => openEditAssignment(a)}>&#9998;</button>
                                <button className="content-icon-btn danger" title="Delete" aria-label="Delete assignment" onClick={() => handleDeleteAssignment(a)}>&#128465;</button>
                              </>
                            )}
                          </div>
                        )}
                      </div>
                      {/* Inline submission form for students (#839) */}
                      {isStudent && submittingAssignmentId === a.id && (
                        <AssignmentSubmission
                          assignmentId={a.id}
                          assignmentTitle={a.title}
                          dueDate={a.due_date}
                          submission={sub || null}
                          onSubmitted={(result) => {
                            setSubmissionMap(prev => ({ ...prev, [a.id]: result }));
                            setSubmittingAssignmentId(null);
                          }}
                          onClose={() => setSubmittingAssignmentId(null)}
                        />
                      )}
                      {/* Teacher submissions list (#839) */}
                      {canManageRoster && !isStudent && expandedSubmissionsId === a.id && (
                        <div className="submission-panel" style={{ marginTop: '8px' }}>
                          <div className="submission-header">
                            <h4>Submissions for: {a.title}</h4>
                            <button className="submission-close-btn" onClick={() => setExpandedSubmissionsId(null)} aria-label="Close">&times;</button>
                          </div>
                          {submissionListMap[a.id] ? (
                            submissionListMap[a.id].length === 0 ? (
                              <p style={{ fontSize: '13px', color: 'var(--color-ink-muted)', fontStyle: 'italic' }}>No submissions yet.</p>
                            ) : (
                              <div className="course-roster-list" style={{ marginTop: '8px' }}>
                                {submissionListMap[a.id].map(s => (
                                  <div key={s.student_id} className="course-roster-row" style={{ padding: '8px 0' }}>
                                    <div className="course-roster-info">
                                      <span className="course-roster-name">{s.student_name}</span>
                                      <span style={{ fontSize: '12px', color: 'var(--color-ink-muted)' }}>
                                        {s.status === 'submitted' && s.submitted_at
                                          ? `Submitted ${new Date(s.submitted_at).toLocaleDateString()}`
                                          : s.status === 'graded'
                                            ? `Graded: ${s.grade ?? '—'}`
                                            : 'Not submitted'}
                                      </span>
                                    </div>
                                    {s.is_late && <span className="submission-badge late">Late</span>}
                                    {s.status !== 'pending' && (
                                      <span className={`submission-badge ${s.status}`}>
                                        {s.status === 'submitted' ? 'Submitted' : s.status === 'graded' ? 'Graded' : s.status}
                                      </span>
                                    )}
                                    {s.has_file && (
                                      <button
                                        className="content-action-btn"
                                        onClick={() => assignmentsApi.downloadSubmission(a.id, s.student_id).catch(() => {})}
                                      >
                                        Download
                                      </button>
                                    )}
                                  </div>
                                ))}
                              </div>
                            )
                          ) : (
                            <p style={{ fontSize: '13px', color: 'var(--color-ink-muted)' }}>Loading...</p>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>

      {/* Enrollment Requests */}
      {canManageRoster && course?.require_approval && enrollmentRequests.length > 0 && (
        <div className="course-section-panel">
          <div className="course-section-header">
            <button className="collapse-toggle" onClick={() => setEnrollReqExpanded(v => !v)}>
              <span className={`section-chevron${enrollReqExpanded ? ' expanded' : ''}`}>&#9654;</span>
              <h3>Enrollment Requests <span className="badge-count">{enrollmentRequests.length}</span></h3>
            </button>
          </div>
          {enrollReqExpanded && (
            <div className="course-roster-list">
              {enrollmentRequests.map(req => (
                <div key={req.id} className="course-roster-row">
                  <div className="course-roster-info">
                    <span className="course-roster-name">{req.student_name || 'Unknown'}</span>
                    <span className="course-roster-email">{req.student_email || ''}</span>
                  </div>
                  <div className="enrollment-req-actions">
                    <button
                      className="courses-btn primary btn-primary btn-sm"
                      onClick={() => handleResolveEnrollmentRequest(req.id, 'approved')}
                      disabled={resolvingReqId === req.id}
                    >
                      Approve
                    </button>
                    <button
                      className="courses-btn secondary btn-secondary btn-sm"
                      onClick={() => handleResolveEnrollmentRequest(req.id, 'rejected')}
                      disabled={resolvingReqId === req.id}
                    >
                      Reject
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Student Roster */}
      {canManageRoster && (
        <div className="course-section-panel">
          <div className="course-section-header">
            <button className="collapse-toggle" onClick={() => setRosterExpanded(v => !v)}>
              <span className={`section-chevron${rosterExpanded ? ' expanded' : ''}`}>&#9654;</span>
              <h3>Enrolled Students ({students.length})</h3>
            </button>
            <button className="courses-btn secondary btn-secondary btn-sm action-icon-btn" onClick={() => { setAddStudentEmail(''); setAddStudentMessage(''); setAddStudentError(''); setAddStudentSuccess(''); setShowAddStudentModal(true); }}>
              <span className="action-icon">+</span> Invite Student
            </button>
          </div>
          {rosterExpanded && (
            <>
              {students.length === 0 ? (
                <p className="course-roster-empty">No students enrolled yet.</p>
              ) : (
                <div className="course-roster-list">
                  {students.map(s => (
                    <div key={s.student_id} className="course-roster-row">
                      <div className="course-roster-info">
                        <span className="course-roster-name">{s.full_name}</span>
                        <span className="course-roster-email">{s.email}</span>
                      </div>
                      {s.grade_level != null && <span className="grade-badge">Grade {s.grade_level}</span>}
                      <button className="course-roster-remove" onClick={() => handleRemoveStudent(s.student_id, s.full_name)}>Remove</button>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}

      </div>

      {/* Add/Invite Student Modal (#551) */}
      {showAddStudentModal && (
        <div className="modal-overlay" onClick={() => setShowAddStudentModal(false)}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Invite Student" ref={addStudentModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>Invite Student</h2>
            <p className="modal-desc">Enter the student's email address. If they don't have an account, an invitation will be sent.</p>
            <div className="modal-form">
              <label>
                Student Email *
                <input
                  type="email"
                  value={addStudentEmail}
                  onChange={(e) => setAddStudentEmail(e.target.value)}
                  placeholder="student@example.com"
                  disabled={addStudentLoading}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddStudent()}
                />
              </label>
              <label>
                Message (optional)
                <input
                  type="text"
                  value={addStudentMessage}
                  onChange={(e) => setAddStudentMessage(e.target.value)}
                  placeholder="e.g., Welcome to the class!"
                  disabled={addStudentLoading}
                />
              </label>
              {addStudentError && <p className="link-error">{addStudentError}</p>}
              {addStudentSuccess && <p className="link-success">{addStudentSuccess}</p>}
            </div>
            <div className="modal-actions">
              <button className="cancel-btn" onClick={() => setShowAddStudentModal(false)} disabled={addStudentLoading}>Close</button>
              <button className="generate-btn" onClick={handleAddStudent} disabled={addStudentLoading || !addStudentEmail.trim()}>
                {addStudentLoading ? 'Sending...' : 'Invite Student'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Course Modal */}
      {showEditModal && (
        <div className="modal-overlay" onClick={() => setShowEditModal(false)}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Edit Class" ref={editCourseModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>Edit Class</h2>
            <div className="modal-form">
              <label>
                Class Name *
                <input type="text" value={editName} onChange={(e) => setEditName(e.target.value)} placeholder="e.g. Math Grade 5" disabled={editSaving} onKeyDown={(e) => e.key === 'Enter' && handleEditCourse()} />
              </label>
              <label>
                Subject
                <input type="text" value={editSubject} onChange={(e) => setEditSubject(e.target.value)} placeholder="e.g. Mathematics" disabled={editSaving} />
              </label>
              <label>
                Description
                <textarea value={editDescription} onChange={(e) => setEditDescription(e.target.value)} placeholder="Class details..." rows={3} disabled={editSaving} />
              </label>
              <label>
                Teacher Email (optional)
                <input type="email" value={editTeacherEmail} onChange={(e) => setEditTeacherEmail(e.target.value)} placeholder="teacher@example.com" disabled={editSaving} />
              </label>
              {editError && <p className="link-error">{editError}</p>}
            </div>
            <div className="modal-actions">
              {!course?.google_classroom_id && (
                <button className="cancel-btn danger-text" onClick={handleDeleteCourse} disabled={editSaving}>
                  Delete Class
                </button>
              )}
              <button className="cancel-btn" onClick={() => setShowEditModal(false)} disabled={editSaving}>Cancel</button>
              <button className="generate-btn" onClick={handleEditCourse} disabled={editSaving || !editName.trim()}>
                {editSaving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Material Modal (standard shared component) */}
      {editingContent && !showContentModal && (
        <EditMaterialModal
          material={editingContent}
          onClose={() => setEditingContent(null)}
          onSaved={() => { setEditingContent(null); loadContents(); }}
        />
      )}

      {/* Add Content Modal */}
      {showContentModal && (
        <div className="modal-overlay" onClick={closeContentModal}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Add Class Details" ref={contentModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>Add Class Details</h2>
            <p className="modal-desc">Add a reference link or resource to this class.</p>
            <div className="modal-form">
              <label>
                Title *
                <input type="text" value={contentTitle} onChange={(e) => setContentTitle(e.target.value)} placeholder="e.g. Chapter 5 Notes" disabled={contentSaving} onKeyDown={(e) => e.key === 'Enter' && handleSaveContent()} />
              </label>
              <label>
                Type
                <select value={contentType} onChange={(e) => setContentType(e.target.value)} disabled={contentSaving}>
                  {CONTENT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </label>
              <label>
                Description (optional)
                <textarea value={contentDescription} onChange={(e) => setContentDescription(e.target.value)} placeholder="Brief description..." rows={2} disabled={contentSaving} />
              </label>
              <label>
                Reference URL (optional)
                <input type="url" value={referenceUrl} onChange={(e) => setReferenceUrl(e.target.value)} placeholder="https://..." disabled={contentSaving} />
              </label>
              <label>
                Google Classroom URL (optional)
                <input type="url" value={googleClassroomUrl} onChange={(e) => setGoogleClassroomUrl(e.target.value)} placeholder="https://classroom.google.com/..." disabled={contentSaving} />
              </label>
              {contentError && <p className="link-error">{contentError}</p>}
            </div>
            <div className="modal-actions">
              <button className="cancel-btn" onClick={closeContentModal} disabled={contentSaving}>Cancel</button>
              <button className="generate-btn" onClick={handleSaveContent} disabled={contentSaving || !contentTitle.trim()}>
                {contentSaving ? 'Saving...' : 'Add Content'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Upload Class Material Modal */}
      {showUploadModal && (
        <div className="modal-overlay" onClick={() => setShowUploadModal(false)}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Upload Class Material" ref={uploadModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>Upload Class Material</h2>
            <p className="modal-desc">Upload a document to extract content. Supports PDF, DOCX, PPTX, TXT, and images.</p>
            <div className="modal-form">
              {!selectedFile ? (
                <div
                  className={`upload-drop-zone ${isDragging ? 'dragging' : ''}`}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <p className="upload-drop-text">Drag & drop a file here, or click to browse</p>
                  <p className="upload-drop-hint">Max {MAX_FILE_SIZE_MB} MB</p>
                  <input
                    ref={fileInputRef}
                    type="file"
                    style={{ display: 'none' }}
                    onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFileSelect(f); }}
                  />
                </div>
              ) : (
                <div className="upload-file-info">
                  <div className="upload-file-name">
                    <strong>{selectedFile.name}</strong>
                    <span className="upload-file-size">({(selectedFile.size / 1024).toFixed(0)} KB)</span>
                    <button className="content-action-btn" onClick={() => { setSelectedFile(null); setExtractedText(''); if (fileInputRef.current) fileInputRef.current.value = ''; }}>Remove</button>
                  </div>
                  {extracting && <p className="upload-extracting">Extracting text...</p>}
                  {extractedText && (
                    <p className="upload-preview">
                      {extractedText.split(/\s+/).length} words extracted
                    </p>
                  )}
                </div>
              )}
              <label>
                Title *
                <input type="text" value={uploadTitle} onChange={(e) => setUploadTitle(e.target.value)} placeholder="Document title" disabled={uploading} />
              </label>
              <label>
                Content Type
                <select value={uploadType} onChange={(e) => setUploadType(e.target.value)} disabled={uploading}>
                  {CONTENT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </label>
              {/* AI Tool Selection (#552) */}
              <label>
                Generate AI Study Material
                <select
                  value={uploadAiTool}
                  onChange={(e) => setUploadAiTool(e.target.value as any)}
                  disabled={uploading || !extractedText}
                  className="upload-ai-tool-select"
                >
                  <option value="none">None - just save the document</option>
                  <option value="study_guide">Study Guide - key concepts, tips & practice questions</option>
                  <option value="quiz">Quiz - multiple choice practice questions</option>
                  <option value="flashcards">Flashcards - term/concept review cards</option>
                </select>
                {!extractedText && selectedFile && !extracting && (
                  <span className="upload-ai-hint">Text extraction required for AI generation</span>
                )}
              </label>
              {uploadAiTool !== 'none' && (
                <label>
                  Custom Instructions (optional)
                  <textarea
                    value={uploadAiCustomPrompt}
                    onChange={(e) => setUploadAiCustomPrompt(e.target.value)}
                    placeholder="e.g. 'Focus on chapters 3-5' or 'Include worked solutions for all math problems'"
                    rows={2}
                    disabled={uploading}
                    className="upload-ai-custom-prompt"
                  />
                </label>
              )}
              {course?.classroom_type === 'school' && (
                <div className="dtap-disclaimer" style={{ marginTop: 8 }}>
                  For school Google Classroom courses, download documents from Google Classroom first, then upload them here to generate study materials.
                </div>
              )}
              {uploadError && <p className="link-error">{uploadError}</p>}
              {/* Parent notification note for students */}
              {user?.role === 'student' && (
                <p className="modal-info-note">
                  Your parent will be notified about this upload.
                </p>
              )}
            </div>
            <div className="modal-actions">
              <button className="cancel-btn" onClick={() => setShowUploadModal(false)} disabled={uploading}>Cancel</button>
              <button className="generate-btn" onClick={handleUploadDocument} disabled={uploading || !selectedFile || !uploadTitle.trim() || extracting}>
                {uploading
                  ? (uploadAiTool !== 'none' ? 'Saving & Queuing AI...' : 'Saving...')
                  : (uploadAiTool !== 'none' ? 'Save & Generate' : 'Save to Class')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Assignment Modal */}
      {showAssignmentModal && (
        <div className="modal-overlay" onClick={() => setShowAssignmentModal(false)}>
          <div className="modal" role="dialog" aria-modal="true" aria-label={editingAssignment ? 'Edit Assignment' : 'Create Assignment'} ref={assignmentModalRef} onClick={(e) => e.stopPropagation()}>
            <h2>{editingAssignment ? 'Edit Assignment' : 'Create Assignment'}</h2>
            <div className="modal-form">
              <label>
                Title *
                <input type="text" value={assignTitle} onChange={(e) => setAssignTitle(e.target.value)} placeholder="e.g. Chapter 5 Homework" disabled={assignSaving} onKeyDown={(e) => e.key === 'Enter' && handleSaveAssignment()} />
              </label>
              <label>
                Description (optional)
                <textarea value={assignDesc} onChange={(e) => setAssignDesc(e.target.value)} placeholder="Assignment details..." rows={3} disabled={assignSaving} />
              </label>
              <label>
                Due Date (optional)
                <input type="datetime-local" value={assignDueDate} onChange={(e) => setAssignDueDate(e.target.value)} disabled={assignSaving} />
              </label>
              <label>
                Max Points (optional)
                <input type="number" min="0" step="1" value={assignMaxPoints} onChange={(e) => setAssignMaxPoints(e.target.value)} placeholder="e.g. 100" disabled={assignSaving} />
              </label>
              {assignError && <p className="link-error">{assignError}</p>}
            </div>
            <div className="modal-actions">
              <button className="cancel-btn" onClick={() => setShowAssignmentModal(false)} disabled={assignSaving}>Cancel</button>
              <button className="generate-btn" onClick={handleSaveAssignment} disabled={assignSaving || !assignTitle.trim()}>
                {assignSaving ? 'Saving...' : editingAssignment ? 'Save Changes' : 'Create Assignment'}
              </button>
            </div>
          </div>
        </div>
      )}

      <CreateTaskModal
        open={!!taskModalContext}
        onClose={() => setTaskModalContext(null)}
        prefillTitle={taskModalContext?.title ?? ''}
        courseId={taskModalContext?.courseId}
        courseContentId={taskModalContext?.courseContentId}
        linkedEntityLabel={taskModalContext?.label}
      />
      {confirmModal}
      <AILimitRequestModal open={showLimitModal} onClose={() => setShowLimitModal(false)} />
    </DashboardLayout>
  );
}
