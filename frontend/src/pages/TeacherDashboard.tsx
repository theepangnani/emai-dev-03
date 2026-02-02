import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { coursesApi, googleApi, messagesApi } from '../api/client';
import { DashboardLayout } from '../components/DashboardLayout';
import './TeacherDashboard.css';

interface Course {
  id: number;
  name: string;
  description: string | null;
  subject: string | null;
  google_classroom_id: string | null;
}

export function TeacherDashboard() {
  const navigate = useNavigate();
  const [courses, setCourses] = useState<Course[]>([]);
  const [googleConnected, setGoogleConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [coursesData, googleStatus] = await Promise.allSettled([
        coursesApi.teachingList(),
        googleApi.getStatus(),
      ]);

      if (coursesData.status === 'fulfilled') {
        setCourses(coursesData.value);
      }
      if (googleStatus.status === 'fulfilled') {
        setGoogleConnected(googleStatus.value.connected);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleConnectGoogle = async () => {
    try {
      const { authorization_url } = await googleApi.getConnectUrl();
      window.location.href = authorization_url;
    } catch {
      // Failed to connect
    }
  };

  const handleSyncCourses = async () => {
    setSyncing(true);
    try {
      await googleApi.syncCourses();
      // Reload courses after sync
      const coursesData = await coursesApi.teachingList();
      setCourses(coursesData);
    } catch {
      // Sync failed
    } finally {
      setSyncing(false);
    }
  };

  if (loading) {
    return (
      <DashboardLayout welcomeSubtitle="Your classroom overview">
        <div className="loading-state">Loading...</div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout welcomeSubtitle="Your classroom overview">
      <div className="dashboard-grid">
        <div className="dashboard-card">
          <div className="card-icon">📚</div>
          <h3>Courses</h3>
          <p className="card-value">{courses.length}</p>
          <p className="card-label">Courses teaching</p>
        </div>

        <div className="dashboard-card clickable" onClick={() => navigate('/messages')}>
          <div className="card-icon">💬</div>
          <h3>Messages</h3>
          <p className="card-value">View</p>
          <p className="card-label">Parent messages</p>
        </div>

        <div className="dashboard-card clickable" onClick={() => navigate('/teacher-communications')}>
          <div className="card-icon">📧</div>
          <h3>Communications</h3>
          <p className="card-value">View</p>
          <p className="card-label">Email monitoring</p>
        </div>

        <div className="dashboard-card">
          <div className="card-icon">🔗</div>
          <h3>Google Classroom</h3>
          <p className="card-value">{googleConnected ? 'Connected' : 'Not Connected'}</p>
          {!googleConnected ? (
            <button className="connect-button" onClick={handleConnectGoogle}>
              Connect
            </button>
          ) : (
            <button className="connect-button" onClick={handleSyncCourses} disabled={syncing}>
              {syncing ? 'Syncing...' : 'Sync Courses'}
            </button>
          )}
        </div>
      </div>

      <div className="dashboard-sections">
        <section className="section teacher-courses-section">
          <h3>Your Courses</h3>
          {courses.length > 0 ? (
            <div className="teacher-courses-grid">
              {courses.map((course) => (
                <div key={course.id} className="teacher-course-card">
                  <h4>{course.name}</h4>
                  {course.subject && <span className="course-subject-tag">{course.subject}</span>}
                  {course.description && (
                    <p className="course-desc">{course.description}</p>
                  )}
                  {course.google_classroom_id && (
                    <span className="google-badge">Google Classroom</span>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <p>No courses assigned yet</p>
              <small>
                {googleConnected
                  ? 'Click "Sync Courses" above to import your Google Classroom courses'
                  : 'Connect Google Classroom to sync your courses'}
              </small>
              {googleConnected && (
                <button className="connect-button" onClick={handleSyncCourses} disabled={syncing} style={{ marginTop: '12px' }}>
                  {syncing ? 'Syncing...' : 'Sync Courses'}
                </button>
              )}
            </div>
          )}
        </section>
      </div>
    </DashboardLayout>
  );
}
