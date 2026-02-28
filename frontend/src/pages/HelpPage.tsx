import { useState } from 'react';
import { DashboardLayout } from '../components/DashboardLayout';
import './HelpPage.css';

interface FaqItem {
  question: string;
  answer: string;
}

interface FaqSection {
  title: string;
  items: FaqItem[];
}

const FAQ_SECTIONS: FaqSection[] = [
  {
    title: 'Getting Started',
    items: [
      {
        question: 'How do I connect my Google Classroom account?',
        answer:
          'Go to your Dashboard and click the "Connect Google Classroom" button. You\'ll be redirected to Google to sign in and grant ClassBridge permission to access your Classroom data. Once connected, your classes and assignments will sync automatically.',
      },
      {
        question: 'How do I sync my classes and assignments?',
        answer:
          'After connecting Google Classroom, your classes sync automatically. To manually refresh, click the sync button on your Dashboard or Classes page. Assignments, due dates, and class materials will be pulled from Google Classroom.',
      },
      {
        question: 'How do I link my child\'s account (for parents)?',
        answer:
          'From your Dashboard, go to "Child Profiles" and click "Invite Child." Enter your child\'s email address to send them an invitation. Once they accept and create their account, you\'ll be able to view their classes, assignments, and progress.',
      },
    ],
  },
  {
    title: 'Study Tools',
    items: [
      {
        question: 'How do I create a study guide from class materials?',
        answer:
          'Navigate to "Class Materials," select a class, and click "Generate Study Guide." ClassBridge uses AI to create a structured study guide from your class content. You can also upload your own files (PDFs, documents) to generate guides from.',
      },
      {
        question: 'How do I take a quiz or use flashcards?',
        answer:
          'Open any study guide and click "Take Quiz" or "Flashcards" to generate interactive study tools from that guide\'s content. Quizzes provide multiple-choice questions with instant feedback, and flashcards let you review key concepts.',
      },
      {
        question: 'How do I upload files for study guide generation?',
        answer:
          'On the "Class Materials" page, click "Upload Material." You can upload PDFs, Word documents, and other text files. ClassBridge will process the content and let you generate AI-powered study guides, quizzes, and flashcards from them.',
      },
    ],
  },
  {
    title: 'Communication',
    items: [
      {
        question: 'How do I send a message to a teacher or parent?',
        answer:
          'Go to "Messages" in the sidebar. Click "New Message" to start a conversation. Select the recipient from the list of connected teachers or parents, type your message, and send. You\'ll receive notifications when they reply.',
      },
      {
        question: 'How do I manage my notification preferences?',
        answer:
          'Click the bell icon in the top-right corner to view your notifications. You can mark notifications as read or dismiss them. Email notifications for important events like new messages and assignment reminders are sent automatically.',
      },
    ],
  },
  {
    title: 'Account & Settings',
    items: [
      {
        question: 'How do I create and track tasks?',
        answer:
          'Go to "Tasks" in the sidebar. Click "New Task" to create a personal task with a title, description, and optional due date. Tasks can be marked as complete as you finish them, helping you stay organized alongside your assignments.',
      },
      {
        question: 'How do I switch between roles (multi-role users)?',
        answer:
          'If you have multiple roles (e.g., both teacher and parent), click on your role badge next to your name in the top-right corner. A dropdown will appear letting you switch between your available roles. Your view will update accordingly.',
      },
      {
        question: 'How do I disconnect or reconnect Google Classroom?',
        answer:
          'To disconnect Google Classroom, go to your Dashboard and look for the Google Classroom connection section. Click "Disconnect" to remove the link. You can reconnect at any time by clicking "Connect Google Classroom" again.',
      },
      {
        question: 'How do I view my child\'s classes and assignments?',
        answer:
          'As a parent, go to "Child Profiles" and select your child. You\'ll see their linked classes, upcoming assignments, and any study materials they\'ve created. This gives you visibility into their academic progress.',
      },
      {
        question: 'How do I change my password or update my profile?',
        answer:
          'Currently, you can reset your password using the "Forgot Password" link on the login page, which sends a reset link to your email. Profile updates including name changes can be managed from your account settings.',
      },
    ],
  },
  {
    title: 'Troubleshooting',
    items: [
      {
        question: 'What should I do if my Google sync fails?',
        answer:
          'First, try clicking the sync button again. If it still fails, your Google authorization may have expired \u2014 go to your Dashboard and reconnect Google Classroom. If the problem persists, sign out and sign back in, then reconnect.',
      },
      {
        question: 'Where can I report a bug or request a feature?',
        answer:
          'Please email us at support@classbridge.ca with a description of the issue or your feature idea. Include screenshots if possible. We review all feedback and use it to improve ClassBridge.',
      },
    ],
  },
];

export function HelpPage() {
  const [expandedIndex, setExpandedIndex] = useState<string | null>(null);

  const toggleItem = (key: string) => {
    setExpandedIndex(prev => (prev === key ? null : key));
  };

  return (
    <DashboardLayout welcomeSubtitle="Find answers to common questions" showBackButton>
      <div className="help-container">
        {FAQ_SECTIONS.map((section, sIdx) => (
          <div key={section.title} className="help-section">
            <h3 className="help-section-title">{section.title}</h3>
            <div className="help-items">
              {section.items.map((item, iIdx) => {
                const key = `${sIdx}-${iIdx}`;
                const isOpen = expandedIndex === key;
                return (
                  <div key={key} className={`help-item${isOpen ? ' open' : ''}`}>
                    <button
                      className="help-question"
                      onClick={() => toggleItem(key)}
                      aria-expanded={isOpen}
                    >
                      <span className={`help-chevron${isOpen ? ' expanded' : ''}`}>&#9654;</span>
                      <span className="help-question-text">{item.question}</span>
                    </button>
                    {isOpen && (
                      <div className="help-answer">
                        <p>{item.answer}</p>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </DashboardLayout>
  );
}
