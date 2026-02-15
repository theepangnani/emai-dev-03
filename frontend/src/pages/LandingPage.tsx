import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './Auth.css';
import './LandingPage.css';

export function LandingPage() {
  const { user } = useAuth();

  if (user) {
    return null; // App.tsx handles redirect for authenticated users
  }

  return (
    <div className="landing-page">
      <nav className="landing-nav">
        <img src="/classbridge-logo.png" alt="ClassBridge" className="landing-nav-logo" />
        <div className="landing-nav-links">
          <Link to="/login" className="landing-btn-secondary">Log In</Link>
          <Link to="/register" className="landing-btn-primary">Get Started</Link>
        </div>
      </nav>

      <section className="landing-hero">
        <img src="/classbridge-hero-logo.png" alt="ClassBridge" className="landing-hero-logo" />
        <h1>Stay connected to your child's education</h1>
        <p className="landing-hero-sub">
          ClassBridge brings parents, students, and teachers together in one platform.
          See assignments, message teachers, and track progress — all in one place.
        </p>
        <div className="landing-hero-actions">
          <Link to="/register" className="landing-btn-primary landing-btn-lg">Get Started Free</Link>
          <Link to="/login" className="landing-btn-secondary landing-btn-lg">Log In</Link>
        </div>
      </section>

      <section className="landing-features">
        <h2>Everything you need, in one place</h2>
        <div className="landing-features-grid">
          <div className="landing-feature">
            <div className="landing-feature-icon">&#128218;</div>
            <h3>Assignments & Grades</h3>
            <p>See all your child's assignments, due dates, and grades across every course. Never miss a deadline.</p>
          </div>
          <div className="landing-feature">
            <div className="landing-feature-icon">&#128172;</div>
            <h3>Teacher Messaging</h3>
            <p>Message teachers directly about your child's progress. No more lost permission slips or missed emails.</p>
          </div>
          <div className="landing-feature">
            <div className="landing-feature-icon">&#128218;</div>
            <h3>AI Study Tools</h3>
            <p>Generate study guides, practice quizzes, and flashcards powered by AI to help students prepare.</p>
          </div>
          <div className="landing-feature">
            <div className="landing-feature-icon">&#128197;</div>
            <h3>Calendar View</h3>
            <p>See everything on a calendar — assignments, tasks, and due dates at a glance.</p>
          </div>
          <div className="landing-feature">
            <div className="landing-feature-icon">&#127891;</div>
            <h3>Google Classroom Sync</h3>
            <p>Connect to Google Classroom and automatically sync courses, assignments, and grades.</p>
          </div>
          <div className="landing-feature">
            <div className="landing-feature-icon">&#128241;</div>
            <h3>Mobile App</h3>
            <p>Access ClassBridge on your phone. Check assignments, read messages, and stay updated on the go.</p>
          </div>
        </div>
      </section>

      <section className="landing-roles">
        <h2>Built for everyone in education</h2>
        <div className="landing-roles-grid">
          <div className="landing-role">
            <h3>For Parents</h3>
            <ul>
              <li>Dashboard showing all children at a glance</li>
              <li>Direct messaging with teachers</li>
              <li>Assignment reminders and notifications</li>
              <li>Mobile app for on-the-go access</li>
            </ul>
          </div>
          <div className="landing-role">
            <h3>For Students</h3>
            <ul>
              <li>All assignments in one place</li>
              <li>AI-powered study tools</li>
              <li>Personal task manager</li>
              <li>Calendar with due dates</li>
            </ul>
          </div>
          <div className="landing-role">
            <h3>For Teachers</h3>
            <ul>
              <li>Google Classroom integration</li>
              <li>Parent communication hub</li>
              <li>Course and assignment management</li>
              <li>Student progress visibility</li>
            </ul>
          </div>
        </div>
      </section>

      <section className="landing-cta">
        <h2>Ready to get started?</h2>
        <p>Join ClassBridge and transform how your school community stays connected.</p>
        <Link to="/register" className="landing-btn-primary landing-btn-lg">Create Your Account</Link>
      </section>

      <footer className="landing-footer">
        <div className="landing-footer-links">
          <Link to="/privacy">Privacy Policy</Link>
          <Link to="/terms">Terms of Service</Link>
          <a href="mailto:support@classbridge.ca">Contact Us</a>
        </div>
        <p>&copy; 2026 ClassBridge by EMAI. All rights reserved.</p>
      </footer>
    </div>
  );
}
