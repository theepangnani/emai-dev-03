import { Link } from 'react-router-dom';
import './Auth.css';
import './Legal.css';

export function PrivacyPolicy() {
  return (
    <div className="auth-container">
      <div className="auth-card legal-card">
        <img src="/classbridge-logo.png" alt="ClassBridge" className="auth-logo" />
        <h1 className="auth-title">Privacy Policy</h1>
        <p className="auth-subtitle">Last updated: February 15, 2026</p>

        <div className="legal-content">
          <section>
            <h2>1. Introduction</h2>
            <p>
              ClassBridge ("we", "us", or "our") is an education management platform
              operated by EMAI. This Privacy Policy explains how we collect, use,
              store, and protect your personal information when you use our web
              application and mobile app (collectively, the "Service").
            </p>
            <p>
              By using ClassBridge, you agree to the collection and use of
              information in accordance with this policy. If you do not agree,
              please do not use the Service.
            </p>
          </section>

          <section>
            <h2>2. Information We Collect</h2>
            <h3>2.1 Account Information</h3>
            <ul>
              <li>Full name and email address (provided during registration)</li>
              <li>Password (stored as a one-way bcrypt hash — we cannot read it)</li>
              <li>User role (parent, student, teacher, or administrator)</li>
            </ul>

            <h3>2.2 Google Classroom Data</h3>
            <p>
              If you connect your Google account, we access the following via the
              Google Classroom and Gmail APIs:
            </p>
            <ul>
              <li>Course names, descriptions, and enrollment information</li>
              <li>Assignment titles, descriptions, and due dates</li>
              <li>Teacher email communications (Gmail — read-only, for teacher accounts only)</li>
            </ul>
            <p>
              We only read this data to display it within ClassBridge. We do not
              modify your Google Classroom courses or assignments.
            </p>

            <h3>2.3 User-Generated Content</h3>
            <ul>
              <li>Messages sent between parents and teachers</li>
              <li>Tasks and to-do items you create</li>
              <li>Files uploaded for AI study material generation</li>
            </ul>

            <h3>2.4 Automatically Collected Data</h3>
            <ul>
              <li>IP address and browser user agent (for security audit logs)</li>
              <li>Timestamps of actions (login, page views, API requests)</li>
            </ul>
          </section>

          <section>
            <h2>3. How We Use Your Information</h2>
            <ul>
              <li><strong>Provide the Service:</strong> Display dashboards, assignments, messages, and notifications</li>
              <li><strong>AI Study Tools:</strong> Generate study guides, quizzes, and flashcards from course materials using OpenAI</li>
              <li><strong>Communication:</strong> Facilitate parent-teacher messaging and deliver email notifications via SendGrid</li>
              <li><strong>Security:</strong> Detect unauthorized access, prevent abuse, and maintain audit logs</li>
              <li><strong>Improvement:</strong> Understand usage patterns to improve the Service</li>
            </ul>
          </section>

          <section>
            <h2>4. Third-Party Services</h2>
            <p>We use the following third-party services to operate ClassBridge:</p>
            <ul>
              <li><strong>Google APIs</strong> (Classroom, Gmail, OAuth) — to sync educational data and authenticate users</li>
              <li><strong>OpenAI API</strong> — to generate AI-powered study materials. Course content sent to OpenAI is processed per their <a href="https://openai.com/policies/api-data-usage-policies" target="_blank" rel="noopener noreferrer">API data usage policy</a> and is not used to train their models.</li>
              <li><strong>SendGrid</strong> — to send transactional emails (notifications, invitations, password resets)</li>
              <li><strong>Google Cloud Platform</strong> — to host the application and database</li>
            </ul>
            <p>
              We do not sell, rent, or share your personal information with
              third parties for their marketing purposes.
            </p>
          </section>

          <section>
            <h2>5. Data Storage and Security</h2>
            <ul>
              <li>Data is stored in a PostgreSQL database hosted on Google Cloud SQL with encryption at rest</li>
              <li>All connections use TLS/SSL encryption in transit</li>
              <li>Passwords are hashed with bcrypt (never stored in plain text)</li>
              <li>JWT tokens are used for session authentication with configurable expiry</li>
              <li>Access is restricted by role-based permissions (RBAC)</li>
              <li>Automated daily database backups with 7-day retention</li>
            </ul>
          </section>

          <section>
            <h2>6. Data Retention</h2>
            <p>
              We retain your data for as long as your account is active. If you
              request account deletion, we will remove your personal data within
              30 days, except where retention is required by law or for legitimate
              security purposes (e.g., audit logs may be retained for up to 90 days).
            </p>
          </section>

          <section>
            <h2>7. Your Rights</h2>
            <p>You have the right to:</p>
            <ul>
              <li><strong>Access</strong> your personal data stored in ClassBridge</li>
              <li><strong>Correct</strong> inaccurate information in your profile</li>
              <li><strong>Delete</strong> your account and associated data</li>
              <li><strong>Export</strong> your data in a portable format</li>
              <li><strong>Revoke</strong> Google account access at any time through your Google Account settings</li>
            </ul>
            <p>
              To exercise any of these rights, contact us at the address below.
            </p>
          </section>

          <section>
            <h2>8. Children's Privacy</h2>
            <p>
              ClassBridge is designed for use by parents, students, and teachers.
              Student accounts are created through parent or teacher invitations.
              We do not knowingly collect personal information from children
              under 13 without parental consent. If you believe a child under 13
              has provided us with personal data without consent, please contact us
              and we will delete the information.
            </p>
          </section>

          <section>
            <h2>9. Changes to This Policy</h2>
            <p>
              We may update this Privacy Policy from time to time. We will notify
              users of material changes by email or through a notice on the Service.
              Your continued use of ClassBridge after changes are posted constitutes
              acceptance of the updated policy.
            </p>
          </section>

          <section>
            <h2>10. Contact Us</h2>
            <p>
              If you have questions about this Privacy Policy or your data, contact us at:
            </p>
            <p>
              <strong>Email:</strong> privacy@classbridge.ca<br />
              <strong>Project:</strong> ClassBridge by EMAI
            </p>
          </section>
        </div>

        <div className="legal-footer">
          <Link to="/terms">Terms of Service</Link>
          <span className="legal-divider">|</span>
          <Link to="/login">Back to Sign In</Link>
        </div>
      </div>
    </div>
  );
}
