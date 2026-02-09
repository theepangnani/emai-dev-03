import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { coursesApi, courseContentsApi, studyApi } from '../api/client';
import type { CourseContentItem } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { DashboardLayout } from '../components/DashboardLayout';
import { CreateTaskModal } from '../components/CreateTaskModal';
import { useConfirm } from '../components/ConfirmModal';
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
  created_by_user_id: number | null;
  is_private: boolean;
  created_at: string;
  google_classroom_id: string | null;
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

  // Edit course modal
  const [showEditModal, setShowEditModal] = useState(false);
  const [editName, setEditName] = useState('');
  const [editSubject, setEditSubject] = useState('');
  const [editDescription, setEditDescription] = useState('');
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

  // Generate study guide state
  const [generatingContentId, setGeneratingContentId] = useState<number | null>(null);

  // Upload: optional study guide generation
  const [generateAfterUpload, setGenerateAfterUpload] = useState(false);
  const [studyGuideType, setStudyGuideType] = useState<'study_guide' | 'quiz' | 'flashcards'>('study_guide');

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
  const canEdit = isCreator || isAdmin;

  // Edit course handlers
  const openEditModal = () => {
    if (!course) return;
    setEditName(course.name);
    setEditSubject(course.subject || '');
    setEditDescription(course.description || '');
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
      });
      setCourse(updated);
      setShowEditModal(false);
    } catch (err: any) {
      setEditError(err.response?.data?.detail || 'Failed to update course');
    } finally {
      setEditSaving(false);
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
    setContentTitle(item.title);
    setContentDescription(item.description || '');
    setContentType(item.content_type);
    setReferenceUrl(item.reference_url || '');
    setGoogleClassroomUrl(item.google_classroom_url || '');
    setContentError('');
    setShowContentModal(true);
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
      title: 'Delete Content',
      message: 'Are you sure you want to delete this content item?',
      confirmLabel: 'Delete',
      variant: 'danger',
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
    setGenerateAfterUpload(false);
    setStudyGuideType('study_guide');
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
      await courseContentsApi.create({
        course_id: courseId,
        title: uploadTitle.trim(),
        description: `Uploaded from: ${selectedFile.name}`,
        text_content: extractedText || undefined,
        content_type: uploadType,
      });
      setShowUploadModal(false);
      await loadContents();

      // If user opted to generate study material, confirm and do it now
      const shouldGenerate = generateAfterUpload && extractedText && await confirm({
        title: 'Generate Study Material',
        message: `Generate ${studyGuideType.replace('_', ' ')} from uploaded content? This will use AI credits.`,
        confirmLabel: 'Generate',
      });
      if (shouldGenerate) {
        setGeneratingContentId(-1); // generic loading indicator
        try {
          let result;
          if (studyGuideType === 'quiz') {
            result = await studyApi.generateQuiz({
              topic: uploadTitle.trim(),
              content: extractedText,
              course_id: courseId,
              num_questions: 10,
            });
            navigate(`/study/quiz/${result.id}`);
          } else if (studyGuideType === 'flashcards') {
            result = await studyApi.generateFlashcards({
              topic: uploadTitle.trim(),
              content: extractedText,
              course_id: courseId,
              num_cards: 15,
            });
            navigate(`/study/flashcards/${result.id}`);
          } else {
            result = await studyApi.generateGuide({
              content: extractedText,
              title: uploadTitle.trim(),
              course_id: courseId,
            });
            navigate(`/study/guide/${result.id}`);
          }
        } catch (err: any) {
          alert(err.response?.data?.detail || 'Failed to generate study material');
        } finally {
          setGeneratingContentId(null);
        }
      }
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
      message: `Generate a study guide from "${item.title}"? This will use AI credits.`,
      confirmLabel: 'Generate',
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
      navigate(`/study/guide/${result.id}`);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to generate study guide');
    } finally {
      setGeneratingContentId(null);
      generatingRef.current = false;
    }
  };

  if (loading) {
    return (
      <DashboardLayout welcomeSubtitle="Course details">
        <div className="loading-state">Loading...</div>
      </DashboardLayout>
    );
  }

  if (!course) {
    return (
      <DashboardLayout welcomeSubtitle="Course not found">
        <div className="course-detail-empty">
          <p>Course not found or you don't have access.</p>
          <button className="courses-btn secondary" onClick={() => navigate('/courses')}>Back to Courses</button>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout welcomeSubtitle={course.name}>
      <div className="course-detail-page">
        {/* Back link */}
        <button className="course-detail-back" onClick={() => navigate('/courses')}>
          &larr; Back to Courses
        </button>

        {/* Course header */}
        <div className="course-detail-header">
          <div className="course-detail-info">
            <h2>{course.name}</h2>
            <div className="course-detail-meta">
              {course.subject && <span className="course-detail-subject">{course.subject}</span>}
              {course.google_classroom_id && <span className="course-detail-badge google">Google Classroom</span>}
              {course.is_private && <span className="course-detail-badge private">Private</span>}
            </div>
            {course.description && <p className="course-detail-desc">{course.description}</p>}
            <span className="course-detail-date">
              Created {new Date(course.created_at).toLocaleDateString()}
            </span>
          </div>
          {canEdit && (
            <button className="courses-btn secondary" onClick={openEditModal}>&#9998; Edit</button>
          )}
        </div>

        {/* Action bar */}
        <div className="course-detail-actions">
          <h3>Course Content</h3>
          <div className="course-detail-action-btns">
            <button className="courses-btn secondary" onClick={openAddContentModal}>+ Add Content</button>
            <button className="courses-btn secondary" onClick={openUploadModal}>+ Upload Document</button>
            <button className="courses-btn secondary" onClick={() => setTaskModalContext({
              courseId: courseId,
              title: `Task for ${course.name}`,
              label: `Course: ${course.name}`,
            })}>+ Create Task</button>
          </div>
        </div>

        {/* Content list */}
        {contentsLoading ? (
          <div className="loading-state" style={{ padding: '20px 0' }}>Loading content...</div>
        ) : contents.length === 0 ? (
          <div className="course-detail-empty-content">
            <p>No content items yet. Add notes, links, resources, or upload documents.</p>
          </div>
        ) : (
          <div className="course-detail-content-list">
            {contents.map((item) => (
              <div key={item.id} className="cd-content-item">
                <div className="cd-content-item-info">
                  <div className="cd-content-item-top">
                    <span className={`content-type-badge ${item.content_type}`}>
                      {CONTENT_TYPES.find(t => t.value === item.content_type)?.label || item.content_type}
                    </span>
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
                    className="courses-btn secondary cd-generate-btn"
                    onClick={() => handleGenerateStudyGuide(item)}
                    disabled={generatingContentId === item.id}
                  >
                    {generatingContentId === item.id ? 'Generating...' : 'Generate Study Guide'}
                  </button>
                  <button
                    className="content-action-btn"
                    onClick={() => setTaskModalContext({
                      courseId: courseId,
                      courseContentId: item.id,
                      title: `Review: ${item.title}`,
                      label: `${item.title} (${course.name})`,
                    })}
                  >
                    + Task
                  </button>
                  {item.created_by_user_id === user?.id && (
                    <>
                      <button className="content-action-btn" onClick={() => openEditContentModal(item)}>Edit</button>
                      <button className="content-action-btn danger" onClick={() => handleDeleteContent(item.id)}>Delete</button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Edit Course Modal */}
      {showEditModal && (
        <div className="modal-overlay" onClick={() => setShowEditModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Edit Course</h2>
            <div className="modal-form">
              <label>
                Course Name *
                <input type="text" value={editName} onChange={(e) => setEditName(e.target.value)} placeholder="e.g. Math Grade 5" disabled={editSaving} onKeyDown={(e) => e.key === 'Enter' && handleEditCourse()} />
              </label>
              <label>
                Subject
                <input type="text" value={editSubject} onChange={(e) => setEditSubject(e.target.value)} placeholder="e.g. Mathematics" disabled={editSaving} />
              </label>
              <label>
                Description
                <textarea value={editDescription} onChange={(e) => setEditDescription(e.target.value)} placeholder="Course details..." rows={3} disabled={editSaving} />
              </label>
              {editError && <p className="link-error">{editError}</p>}
            </div>
            <div className="modal-actions">
              <button className="cancel-btn" onClick={() => setShowEditModal(false)} disabled={editSaving}>Cancel</button>
              <button className="generate-btn" onClick={handleEditCourse} disabled={editSaving || !editName.trim()}>
                {editSaving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add/Edit Content Modal */}
      {showContentModal && (
        <div className="modal-overlay" onClick={closeContentModal}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>{editingContent ? 'Edit Content' : 'Add Content'}</h2>
            <p className="modal-desc">Add a reference link or resource to this course.</p>
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
                {contentSaving ? 'Saving...' : editingContent ? 'Save Changes' : 'Add Content'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Upload Document Modal */}
      {showUploadModal && (
        <div className="modal-overlay" onClick={() => setShowUploadModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Upload Document</h2>
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
              {/* Optional: generate study guide */}
              <label className="upload-checkbox-label">
                <input
                  type="checkbox"
                  checked={generateAfterUpload}
                  onChange={(e) => setGenerateAfterUpload(e.target.checked)}
                  disabled={uploading || !extractedText}
                />
                Generate study material from this document
              </label>
              {generateAfterUpload && (
                <label>
                  Study Material Type
                  <select value={studyGuideType} onChange={(e) => setStudyGuideType(e.target.value as any)} disabled={uploading}>
                    <option value="study_guide">Study Guide</option>
                    <option value="quiz">Quiz</option>
                    <option value="flashcards">Flashcards</option>
                  </select>
                </label>
              )}
              {uploadError && <p className="link-error">{uploadError}</p>}
            </div>
            <div className="modal-actions">
              <button className="cancel-btn" onClick={() => setShowUploadModal(false)} disabled={uploading}>Cancel</button>
              <button className="generate-btn" onClick={handleUploadDocument} disabled={uploading || !selectedFile || !uploadTitle.trim() || extracting}>
                {uploading ? (generateAfterUpload ? 'Saving & Generating...' : 'Saving...') : (generateAfterUpload ? 'Save & Generate' : 'Save to Course')}
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
    </DashboardLayout>
  );
}
