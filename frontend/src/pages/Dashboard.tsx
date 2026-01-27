import { useState, useEffect, useRef } from 'react';
import { useSearchParams, Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { googleApi, coursesApi, assignmentsApi, studyApi } from '../api/client';
import type { StudyGuide, SupportedFormats } from '../api/client';
import { StudyToolsButton } from '../components/StudyToolsButton';
import { logger } from '../utils/logger';
import './Dashboard.css';

const MAX_FILE_SIZE_MB = 100;

interface Course {
  id: number;
  name: string;
  google_classroom_id?: string;
}

interface Assignment {
  id: number;
  title: string;
  description: string | null;
  course_id: number;
  due_date: string | null;
}

export function Dashboard() {
  const { user, logout } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const [googleConnected, setGoogleConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [courses, setCourses] = useState<Course[]>([]);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [studyGuides, setStudyGuides] = useState<StudyGuide[]>([]);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Custom study material modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [customTitle, setCustomTitle] = useState('');
  const [customContent, setCustomContent] = useState('');
  const [customType, setCustomType] = useState<'study_guide' | 'quiz' | 'flashcards'>('study_guide');
  const [isGenerating, setIsGenerating] = useState(false);

  // File upload state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadMode, setUploadMode] = useState<'text' | 'file'>('text');
  const [isDragging, setIsDragging] = useState(false);
  const [supportedFormats, setSupportedFormats] = useState<SupportedFormats | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Check Google connection status on mount and handle OAuth callback
  useEffect(() => {
    const checkGoogleStatus = async () => {
      try {
        const status = await googleApi.getStatus();
        setGoogleConnected(status.connected);
      } catch {
        setGoogleConnected(false);
      }
    };

    // Handle OAuth callback params
    const connected = searchParams.get('google_connected');
    const error = searchParams.get('error');

    if (connected === 'true') {
      setGoogleConnected(true);
      setStatusMessage({ type: 'success', text: 'Google Classroom connected successfully!' });
      // Clear the URL params
      setSearchParams({});
    } else if (error) {
      setStatusMessage({ type: 'error', text: `Connection failed: ${error}` });
      setSearchParams({});
    }

    checkGoogleStatus();
    loadCourses();
    loadAssignments();
    loadStudyGuides();
  }, [searchParams, setSearchParams]);

  const loadCourses = async () => {
    try {
      const data = await coursesApi.list();
      setCourses(data);
      logger.debug('Courses loaded', { count: data.length });
    } catch (err) {
      logger.logError(err, 'Failed to load courses', { component: 'Dashboard' });
    }
  };

  const loadAssignments = async () => {
    try {
      const data = await assignmentsApi.list();
      setAssignments(data);
    } catch {
      // Assignments not loaded, that's okay
    }
  };

  const loadStudyGuides = async () => {
    try {
      const data = await studyApi.listGuides();
      setStudyGuides(data);
    } catch {
      // Study guides not loaded, that's okay
    }
  };

  const handleConnectGoogle = async () => {
    setIsConnecting(true);
    try {
      const { authorization_url } = await googleApi.getConnectUrl();
      window.location.href = authorization_url;
    } catch {
      setStatusMessage({ type: 'error', text: 'Failed to initiate Google connection' });
      setIsConnecting(false);
    }
  };

  const handleDisconnectGoogle = async () => {
    try {
      await googleApi.disconnect();
      setGoogleConnected(false);
      setStatusMessage({ type: 'success', text: 'Google Classroom disconnected' });
    } catch {
      setStatusMessage({ type: 'error', text: 'Failed to disconnect Google Classroom' });
    }
  };

  const handleSyncCourses = async () => {
    setIsSyncing(true);
    setStatusMessage(null);
    try {
      const result = await googleApi.syncCourses();
      setStatusMessage({ type: 'success', text: result.message || 'Courses synced successfully' });
      loadCourses();
    } catch {
      setStatusMessage({ type: 'error', text: 'Failed to sync courses' });
    } finally {
      setIsSyncing(false);
    }
  };

  // Clear status message after 5 seconds
  useEffect(() => {
    if (statusMessage) {
      const timer = setTimeout(() => setStatusMessage(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [statusMessage]);

  // Load supported formats when modal opens
  useEffect(() => {
    if (showCreateModal && !supportedFormats) {
      studyApi.getSupportedFormats().then(setSupportedFormats).catch(() => {});
    }
  }, [showCreateModal, supportedFormats]);

  // File upload handlers
  const handleFileSelect = (file: File) => {
    const fileSizeMB = file.size / (1024 * 1024);
    logger.info('File selected for upload', { filename: file.name, sizeMB: fileSizeMB.toFixed(2) });

    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      logger.warn('File too large', { filename: file.name, sizeMB: fileSizeMB.toFixed(2), maxMB: MAX_FILE_SIZE_MB });
      setStatusMessage({ type: 'error', text: `File size exceeds ${MAX_FILE_SIZE_MB} MB limit` });
      return;
    }
    setSelectedFile(file);
    setUploadMode('file');
    // Auto-set title from filename if not already set
    if (!customTitle) {
      const baseName = file.name.replace(/\.[^/.]+$/, '');
      setCustomTitle(baseName);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  const clearFileSelection = () => {
    setSelectedFile(null);
    setUploadMode('text');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const resetModal = () => {
    setShowCreateModal(false);
    setCustomTitle('');
    setCustomContent('');
    setSelectedFile(null);
    setUploadMode('text');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleCreateCustom = async () => {
    // Validate input based on mode
    if (uploadMode === 'file') {
      if (!selectedFile) {
        setStatusMessage({ type: 'error', text: 'Please select a file to upload' });
        return;
      }
    } else {
      if (!customContent.trim()) {
        setStatusMessage({ type: 'error', text: 'Please enter some content' });
        return;
      }
    }

    logger.info('Generating study material', {
      mode: uploadMode,
      type: customType,
      filename: selectedFile?.name,
      contentLength: customContent.length,
    });

    setIsGenerating(true);
    try {
      let result;

      if (uploadMode === 'file' && selectedFile) {
        // Use file upload API
        result = await studyApi.generateFromFile({
          file: selectedFile,
          title: customTitle || undefined,
          guide_type: customType,
          num_questions: 5,
          num_cards: 10,
        });
      } else {
        // Use text content API
        if (customType === 'quiz') {
          result = await studyApi.generateQuiz({
            topic: customTitle || 'Custom Quiz',
            content: customContent,
            num_questions: 5,
          });
        } else if (customType === 'flashcards') {
          result = await studyApi.generateFlashcards({
            topic: customTitle || 'Custom Flashcards',
            content: customContent,
            num_cards: 10,
          });
        } else {
          result = await studyApi.generateGuide({
            title: customTitle || 'Custom Study Guide',
            content: customContent,
          });
        }
      }

      logger.info('Study material generated successfully', { id: result.id, type: customType });

      // Navigate to the appropriate page
      if (customType === 'quiz') {
        navigate(`/study/quiz/${result.id}`);
      } else if (customType === 'flashcards') {
        navigate(`/study/flashcards/${result.id}`);
      } else {
        navigate(`/study/guide/${result.id}`);
      }

      resetModal();
    } catch (err) {
      logger.logError(err, 'Failed to generate study material', { mode: uploadMode, type: customType });
      setStatusMessage({ type: 'error', text: 'Failed to generate study material' });
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <div className="header-left">
          <h1 className="logo">EMAI</h1>
        </div>
        <div className="header-right">
          <span className="user-name">{user?.full_name}</span>
          <span className="user-role">{user?.role}</span>
          <button onClick={logout} className="logout-button">
            Sign Out
          </button>
        </div>
      </header>

      <main className="dashboard-main">
        {statusMessage && (
          <div className={`status-message status-${statusMessage.type}`}>
            {statusMessage.text}
          </div>
        )}

        <div className="welcome-section">
          <h2>Welcome back, {user?.full_name?.split(' ')[0]}!</h2>
          <p>Here's your learning overview</p>
        </div>

        <div className="dashboard-grid">
          <div className="dashboard-card">
            <div className="card-icon">📚</div>
            <h3>Courses</h3>
            <p className="card-value">{courses.length || '--'}</p>
            <p className="card-label">Active courses</p>
          </div>

          <div className="dashboard-card">
            <div className="card-icon">📝</div>
            <h3>Assignments</h3>
            <p className="card-value">{assignments.length || '--'}</p>
            <p className="card-label">Total assignments</p>
          </div>

          <div className="dashboard-card">
            <div className="card-icon">📊</div>
            <h3>Average Grade</h3>
            <p className="card-value">--</p>
            <p className="card-label">Overall performance</p>
          </div>

          <div className="dashboard-card">
            <div className="card-icon">🔗</div>
            <h3>Google Classroom</h3>
            <p className="card-value">{googleConnected ? 'Connected' : 'Not Connected'}</p>
            {googleConnected ? (
              <div className="card-buttons">
                <button
                  className="connect-button"
                  onClick={handleSyncCourses}
                  disabled={isSyncing}
                >
                  {isSyncing ? 'Syncing...' : 'Sync Courses'}
                </button>
                <button
                  className="disconnect-button"
                  onClick={handleDisconnectGoogle}
                >
                  Disconnect
                </button>
              </div>
            ) : (
              <button
                className="connect-button"
                onClick={handleConnectGoogle}
                disabled={isConnecting}
              >
                {isConnecting ? 'Connecting...' : 'Connect'}
              </button>
            )}
          </div>
        </div>

        <div className="dashboard-sections">
          <section className="section">
            <h3>Your Assignments</h3>
            {assignments.length > 0 ? (
              <ul className="assignments-list">
                {assignments.map((assignment) => (
                  <li key={assignment.id} className="assignment-item">
                    <div className="assignment-info">
                      <span className="assignment-title">{assignment.title}</span>
                      {assignment.due_date && (
                        <span className="assignment-due">
                          Due: {new Date(assignment.due_date).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                    <StudyToolsButton
                      assignmentId={assignment.id}
                      assignmentTitle={assignment.title}
                    />
                  </li>
                ))}
              </ul>
            ) : (
              <div className="empty-state">
                <p>No assignments yet</p>
                <small>Sync your Google Classroom to see assignments</small>
              </div>
            )}
          </section>

          <section className="section">
            <div className="section-header">
              <h3>Your Study Materials</h3>
              <button className="create-custom-btn" onClick={() => setShowCreateModal(true)}>
                + Create Custom
              </button>
            </div>
            {studyGuides.length > 0 ? (
              <ul className="study-guides-list">
                {studyGuides.map((guide) => (
                  <li key={guide.id} className="study-guide-item">
                    <Link
                      to={
                        guide.guide_type === 'quiz'
                          ? `/study/quiz/${guide.id}`
                          : guide.guide_type === 'flashcards'
                          ? `/study/flashcards/${guide.id}`
                          : `/study/guide/${guide.id}`
                      }
                      className="study-guide-link"
                    >
                      <span className="guide-icon">
                        {guide.guide_type === 'quiz' ? '❓' : guide.guide_type === 'flashcards' ? '🃏' : '📖'}
                      </span>
                      <span className="guide-title">{guide.title}</span>
                      <span className="guide-date">
                        {new Date(guide.created_at).toLocaleDateString()}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="empty-state">
                <p>No study materials yet</p>
                <small>Click "Create Custom" to generate study guides from any content</small>
              </div>
            )}
          </section>

          <section className="section">
            <h3>Your Courses</h3>
            {courses.length > 0 ? (
              <ul className="courses-list">
                {courses.map((course) => (
                  <li key={course.id} className="course-item">
                    <span className="course-name">{course.name}</span>
                    {course.google_classroom_id && (
                      <span className="google-badge">Google</span>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <div className="empty-state">
                <p>No courses yet</p>
                <small>Connect Google Classroom to sync your courses</small>
              </div>
            )}
          </section>
        </div>
      </main>

      {/* Create Custom Study Material Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => resetModal()}>
          <div className="modal modal-lg" onClick={(e) => e.stopPropagation()}>
            <h2>Create Study Material</h2>

            {/* Mode Toggle */}
            <div className="mode-toggle">
              <button
                className={`mode-btn ${uploadMode === 'text' ? 'active' : ''}`}
                onClick={() => setUploadMode('text')}
                disabled={isGenerating}
              >
                Paste Text
              </button>
              <button
                className={`mode-btn ${uploadMode === 'file' ? 'active' : ''}`}
                onClick={() => setUploadMode('file')}
                disabled={isGenerating}
              >
                Upload File
              </button>
            </div>

            <div className="modal-form">
              <label>
                Title (optional)
                <input
                  type="text"
                  value={customTitle}
                  onChange={(e) => setCustomTitle(e.target.value)}
                  placeholder="e.g., Chapter 5 Review"
                  disabled={isGenerating}
                />
              </label>

              {uploadMode === 'text' ? (
                <label>
                  Content to study
                  <textarea
                    value={customContent}
                    onChange={(e) => setCustomContent(e.target.value)}
                    placeholder="Paste your notes, textbook content, or any material you want to study..."
                    rows={8}
                    disabled={isGenerating}
                  />
                </label>
              ) : (
                <div className="file-upload-section">
                  <input
                    ref={fileInputRef}
                    type="file"
                    onChange={handleFileInputChange}
                    accept=".pdf,.docx,.doc,.txt,.md,.xlsx,.xls,.csv,.pptx,.ppt,.png,.jpg,.jpeg,.gif,.bmp,.tiff,.webp,.zip"
                    style={{ display: 'none' }}
                    disabled={isGenerating}
                  />

                  <div
                    className={`drop-zone ${isDragging ? 'dragging' : ''} ${selectedFile ? 'has-file' : ''}`}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    onClick={() => !isGenerating && fileInputRef.current?.click()}
                  >
                    {selectedFile ? (
                      <div className="selected-file">
                        <span className="file-icon">📄</span>
                        <div className="file-info">
                          <span className="file-name">{selectedFile.name}</span>
                          <span className="file-size">
                            {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                          </span>
                        </div>
                        <button
                          className="clear-file-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            clearFileSelection();
                          }}
                          disabled={isGenerating}
                        >
                          ×
                        </button>
                      </div>
                    ) : (
                      <div className="drop-zone-content">
                        <span className="upload-icon">📁</span>
                        <p>Drag & drop a file here, or click to browse</p>
                        <small>
                          Supports: PDF, Word, Excel, PowerPoint, Images, Text, ZIP
                          <br />
                          Max size: {MAX_FILE_SIZE_MB} MB
                        </small>
                      </div>
                    )}
                  </div>
                </div>
              )}

              <label>
                Generate as
                <select
                  value={customType}
                  onChange={(e) => setCustomType(e.target.value as 'study_guide' | 'quiz' | 'flashcards')}
                  disabled={isGenerating}
                >
                  <option value="study_guide">Study Guide</option>
                  <option value="quiz">Practice Quiz</option>
                  <option value="flashcards">Flashcards</option>
                </select>
              </label>
            </div>

            <div className="modal-actions">
              <button className="cancel-btn" onClick={() => resetModal()} disabled={isGenerating}>
                Cancel
              </button>
              <button
                className="generate-btn"
                onClick={handleCreateCustom}
                disabled={isGenerating || (uploadMode === 'file' ? !selectedFile : !customContent.trim())}
              >
                {isGenerating ? 'Generating...' : 'Generate'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
