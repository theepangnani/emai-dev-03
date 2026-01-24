import { useAuth } from '../context/AuthContext';
import './Dashboard.css';

export function Dashboard() {
  const { user, logout } = useAuth();

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
        <div className="welcome-section">
          <h2>Welcome back, {user?.full_name?.split(' ')[0]}!</h2>
          <p>Here's your learning overview</p>
        </div>

        <div className="dashboard-grid">
          <div className="dashboard-card">
            <div className="card-icon">📚</div>
            <h3>Courses</h3>
            <p className="card-value">--</p>
            <p className="card-label">Active courses</p>
          </div>

          <div className="dashboard-card">
            <div className="card-icon">📝</div>
            <h3>Assignments</h3>
            <p className="card-value">--</p>
            <p className="card-label">Due this week</p>
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
            <p className="card-value">Not Connected</p>
            <button className="connect-button">Connect</button>
          </div>
        </div>

        <div className="dashboard-sections">
          <section className="section">
            <h3>Upcoming Assignments</h3>
            <div className="empty-state">
              <p>No upcoming assignments</p>
              <small>Connect Google Classroom to sync your assignments</small>
            </div>
          </section>

          <section className="section">
            <h3>Recent Activity</h3>
            <div className="empty-state">
              <p>No recent activity</p>
              <small>Your learning activity will appear here</small>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
