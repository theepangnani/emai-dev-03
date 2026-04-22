import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useFeature } from '../hooks/useFeatureToggle';
import { useVariantBucket } from '../hooks/useVariantBucket';
import { TuesdayMirror } from '../components/demo/TuesdayMirror';
import { InstantTrialSection } from '../components/demo/InstantTrialSection';
import { InstantTrialModal } from '../components/demo/InstantTrialModal';
import RoleSwitcher from '../components/demo/RoleSwitcher';
import { ProofWall } from '../components/demo/ProofWall';
import './LaunchLandingPage.css';

export function LaunchLandingPage() {
  const { user } = useAuth();
  // #3895 — hydration flicker is handled centrally in `useFeature`:
  // `waitlist_enabled` defaults to `true` during the feature-toggle query
  // load, so "Get Started" no longer flashes before the server response.
  const waitlistEnabled = useFeature('waitlist_enabled');
  const demoLandingVariant = useVariantBucket('demo_landing_v1_1');
  const [demoOpen, setDemoOpen] = useState(false);
  const openDemo = () => setDemoOpen(true);

  if (user) {
    return null; // App.tsx handles redirect for authenticated users
  }

  return (
    <div className="launch-page">
      <nav className="launch-nav">
        <img src="/classbridge-logo-v6.png" alt="ClassBridge" className="launch-nav-logo" />
        <div className="launch-nav-links">
          <Link to="/login" className="launch-btn-secondary">Log In</Link>
        </div>
      </nav>

      <section className="launch-hero">
        <img src="/classbridge-hero-logo.png" alt="ClassBridge" className="launch-hero-logo" />
        <h1>The AI-Powered Education Platform</h1>
        <p className="launch-hero-sub">
          Connecting parents, students, and teachers in one intelligent platform.
          Stay on top of assignments, communicate with teachers, and unlock AI-powered study tools.
        </p>
        <div className="launch-hero-actions">
          {waitlistEnabled ? (
            <Link to="/waitlist" className="launch-btn-primary launch-btn-lg">Join the Waitlist</Link>
          ) : (
            <Link to="/register" className="launch-btn-primary launch-btn-lg">Get Started</Link>
          )}
          <Link to="/login" className="launch-btn-secondary launch-btn-lg">Login</Link>
          <Link to="/survey" className="launch-btn-secondary launch-btn-lg">Take Our Survey</Link>
        </div>
      </section>

      {demoLandingVariant === 'on' && (
        <>
          <TuesdayMirror />
          <section id="instant-trial">
            <InstantTrialSection onOpen={openDemo} />
          </section>
          <RoleSwitcher onCtaClick={openDemo} />
          <ProofWall />
        </>
      )}

      <section className="launch-features">
        <h2>Why ClassBridge?</h2>
        <div className="launch-features-grid">
          <div className="launch-feature">
            <div className="launch-feature-icon">&#129302;</div>
            <h3>AI Study Tools</h3>
            <p>Generate study guides, practice quizzes, and flashcards powered by AI to help students prepare for any topic.</p>
          </div>
          <div className="launch-feature">
            <div className="launch-feature-icon">&#127891;</div>
            <h3>LMS Integration</h3>
            <p>Sync courses, assignments, and grades from third-party platforms like Google Classroom, Brightspace, and more into one unified dashboard.</p>
          </div>
          <div className="launch-feature">
            <div className="launch-feature-icon">&#128172;</div>
            <h3>Parent-Teacher Communication</h3>
            <p>Message teachers directly, receive assignment reminders, and stay informed about your child's progress.</p>
          </div>
          <div className="launch-feature">
            <div className="launch-feature-icon">&#9745;</div>
            <h3>Smart Task Management</h3>
            <p>Track assignments, set priorities, and manage due dates with a personal task manager built for students.</p>
          </div>
        </div>
      </section>

      <footer className="launch-footer">
        <p className="launch-footer-brand">ClassBridge</p>
        <div className="launch-footer-links">
          <Link to="/privacy">Privacy Policy</Link>
          <Link to="/terms">Terms of Service</Link>
        </div>
        <p className="launch-footer-copy">&copy; 2026 ClassBridge by EMAI. All rights reserved.</p>
      </footer>
      {demoLandingVariant === 'on' && demoOpen && (
        <InstantTrialModal onClose={() => setDemoOpen(false)} />
      )}
    </div>
  );
}
