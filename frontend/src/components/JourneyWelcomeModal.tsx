import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useFABContext } from '../context/FABContext';
import { useJourneyHint } from '../hooks/useJourneyHint';
import './JourneyWelcomeModal.css';

interface JourneyStep {
  id: string;
  title: string;
  description: string;
  askQuestion: string;
}

const ROLE_STEPS: Record<string, JourneyStep[]> = {
  parent: [
    { id: 'P02', title: 'Add Your Child', description: 'Link your child\'s account to see their progress.', askQuestion: 'How do I add my child to ClassBridge?' },
    { id: 'P03', title: 'Upload Materials', description: 'Upload study materials for your child to practice with.', askQuestion: 'How do I upload study materials for my child?' },
    { id: 'P05', title: 'Explore Dashboard', description: 'View grades, assignments, and insights at a glance.', askQuestion: 'What can I see on my parent dashboard?' },
  ],
  student: [
    { id: 'S09', title: 'Your Dashboard', description: 'See your classes, assignments, and study tools in one place.', askQuestion: 'What can I do from my student dashboard?' },
    { id: 'S02', title: 'Create a Study Guide', description: 'Generate AI-powered study guides from your materials.', askQuestion: 'How do I create a study guide?' },
    { id: 'S03', title: 'Take a Practice Quiz', description: 'Test your knowledge with AI-generated quizzes.', askQuestion: 'How do I take a practice quiz?' },
  ],
  teacher: [
    { id: 'T02', title: 'Create a Class', description: 'Set up your first class to start managing students.', askQuestion: 'How do I create a class in ClassBridge?' },
    { id: 'T03', title: 'Upload Materials', description: 'Share study materials and resources with your students.', askQuestion: 'How do I upload materials for my class?' },
    { id: 'T07', title: 'Invite Students', description: 'Add students to your class with a join code or link.', askQuestion: 'How do I invite students to my class?' },
  ],
  admin: [
    { id: 'A01', title: 'Admin Dashboard', description: 'Monitor platform usage, users, and system health.', askQuestion: 'What can I do from the admin dashboard?' },
    { id: 'A02', title: 'Manage Users', description: 'Add, edit, or deactivate user accounts.', askQuestion: 'How do I manage users as an admin?' },
  ],
};

const ROLE_SUBTITLES: Record<string, string> = {
  parent: "Here's how to get started as a parent",
  student: "Here's how to get started as a student",
  teacher: "Here's how to get started as a teacher",
  admin: "Here's how to manage your platform",
};

function DiagramThumbnail({ journeyId }: { journeyId: string }) {
  const [errored, setErrored] = useState(false);

  if (errored) {
    return (
      <div className="journey-step-thumbnail-fallback" aria-hidden="true">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="16" y1="13" x2="8" y2="13" />
          <line x1="16" y1="17" x2="8" y2="17" />
        </svg>
      </div>
    );
  }

  return (
    <img
      className="journey-step-thumbnail"
      src={`/help/journeys/${journeyId}.svg`}
      alt={`Journey ${journeyId} diagram`}
      onError={() => setErrored(true)}
    />
  );
}

export function JourneyWelcomeModal() {
  const { user } = useAuth();
  const { openChatWithQuestion } = useFABContext();
  const navigate = useNavigate();
  const { hint, dismiss, suppressAll } = useJourneyHint('dashboard');
  const [visible, setVisible] = useState(false);

  // Show modal when hint is the welcome_modal
  useEffect(() => {
    if (hint && hint.hint_key === 'welcome_modal') {
      setVisible(true);
    }
  }, [hint]);

  // Also show on first login if no backend hint (fallback for when API doesn't exist yet)
  useEffect(() => {
    if (!user) return;
    const storageKey = `welcome_modal_shown_${user.id}`;
    if (localStorage.getItem(storageKey)) return;

    // Give the hint API a moment to respond; if no hint, show fallback
    const timer = setTimeout(() => {
      if (!hint) {
        setVisible(true);
        localStorage.setItem(storageKey, '1');
      }
    }, 1500);
    return () => clearTimeout(timer);
  }, [user, hint]);

  // Close on Escape
  useEffect(() => {
    if (!visible) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        handleDismiss();
      }
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible]);

  const handleDismiss = useCallback(() => {
    setVisible(false);
    if (hint) dismiss();
    if (user) {
      localStorage.setItem(`welcome_modal_shown_${user.id}`, '1');
    }
  }, [hint, dismiss, user]);

  const handleSuppressAll = useCallback(() => {
    setVisible(false);
    suppressAll();
    if (user) {
      localStorage.setItem(`welcome_modal_shown_${user.id}`, '1');
    }
  }, [suppressAll, user]);

  const handleShowMe = useCallback((journeyId: string) => {
    setVisible(false);
    if (hint) dismiss();
    if (user) {
      localStorage.setItem(`welcome_modal_shown_${user.id}`, '1');
    }
    navigate(`/help#journey-${journeyId}`);
  }, [navigate, hint, dismiss, user]);

  const handleAskBot = useCallback((question: string) => {
    setVisible(false);
    if (hint) dismiss();
    if (user) {
      localStorage.setItem(`welcome_modal_shown_${user.id}`, '1');
    }
    openChatWithQuestion(question);
  }, [openChatWithQuestion, hint, dismiss, user]);

  if (!visible || !user) return null;

  const role = user.role || 'parent';
  const steps = ROLE_STEPS[role] || ROLE_STEPS.parent;
  const subtitle = ROLE_SUBTITLES[role] || ROLE_SUBTITLES.parent;

  return (
    <div
      className="journey-welcome-overlay"
      onClick={(e) => { if (e.target === e.currentTarget) handleDismiss(); }}
      role="dialog"
      aria-modal="true"
      aria-label="Welcome to ClassBridge"
    >
      <div className="journey-welcome-modal">
        <div className="journey-welcome-header">
          <h2>Welcome to ClassBridge!</h2>
          <p className="journey-welcome-subtitle">{subtitle}</p>
        </div>

        <div className="journey-welcome-body">
          {steps.map((step) => (
            <div key={step.id} className="journey-step-card">
              <DiagramThumbnail journeyId={step.id} />
              <p className="journey-step-title">{step.title}</p>
              <p className="journey-step-desc">{step.description}</p>
              <div className="journey-step-actions">
                <button
                  className="journey-btn-show"
                  onClick={() => handleShowMe(step.id)}
                >
                  Show me how
                </button>
                <button
                  className="journey-btn-ask"
                  onClick={() => handleAskBot(step.askQuestion)}
                >
                  Ask the Bot
                </button>
              </div>
            </div>
          ))}
        </div>

        <div className="journey-welcome-footer">
          <button className="journey-footer-explore" onClick={handleDismiss}>
            Got it, let me explore
          </button>
          <button className="journey-footer-suppress" onClick={handleSuppressAll}>
            Don't show tips
          </button>
        </div>
      </div>
    </div>
  );
}
