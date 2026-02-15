import { Link } from 'react-router-dom';
import './Auth.css';
import './Legal.css';

export function TermsOfService() {
  return (
    <div className="auth-container">
      <div className="auth-card legal-card">
        <img src="/classbridge-logo.png" alt="ClassBridge" className="auth-logo" />
        <h1 className="auth-title">Terms of Service</h1>
        <p className="auth-subtitle">Last updated: February 15, 2026</p>

        <div className="legal-content">
          <section>
            <h2>1. Acceptance of Terms</h2>
            <p>
              By accessing or using ClassBridge (the "Service"), operated by EMAI,
              you agree to be bound by these Terms of Service ("Terms"). If you do
              not agree to these Terms, do not use the Service.
            </p>
          </section>

          <section>
            <h2>2. Description of Service</h2>
            <p>
              ClassBridge is an education management platform that connects parents,
              students, teachers, and administrators. The Service provides:
            </p>
            <ul>
              <li>Google Classroom integration for course and assignment tracking</li>
              <li>AI-powered study tools (study guides, quizzes, flashcards)</li>
              <li>Parent-teacher messaging</li>
              <li>Task management and calendar views</li>
              <li>Email and announcement monitoring for teachers</li>
              <li>Notification system for assignments and communications</li>
            </ul>
          </section>

          <section>
            <h2>3. User Accounts</h2>
            <ul>
              <li>You must provide accurate and complete registration information</li>
              <li>You are responsible for maintaining the security of your account credentials</li>
              <li>You must not share your account with others or allow unauthorized access</li>
              <li>You must notify us immediately of any unauthorized use of your account</li>
              <li>Accounts are assigned roles (parent, student, teacher, admin) that determine access levels</li>
            </ul>
          </section>

          <section>
            <h2>4. Acceptable Use</h2>
            <p>You agree not to:</p>
            <ul>
              <li>Use the Service for any unlawful purpose</li>
              <li>Attempt to access another user's account or data</li>
              <li>Interfere with the operation of the Service or its infrastructure</li>
              <li>Upload malicious content, viruses, or harmful code</li>
              <li>Use automated tools to scrape or extract data from the Service</li>
              <li>Impersonate another person or misrepresent your role</li>
              <li>Use the AI study tools to generate inappropriate or harmful content</li>
            </ul>
          </section>

          <section>
            <h2>5. Google Account Integration</h2>
            <p>
              By connecting your Google account to ClassBridge, you authorize us to
              access your Google Classroom and Gmail data as described in our{' '}
              <Link to="/privacy">Privacy Policy</Link>. You can revoke this access
              at any time through your Google Account settings. Disconnecting your
              Google account will stop data synchronization but will not delete
              previously synced data from ClassBridge.
            </p>
          </section>

          <section>
            <h2>6. AI-Generated Content</h2>
            <p>
              ClassBridge uses artificial intelligence (OpenAI) to generate study
              materials from your course content. Please note:
            </p>
            <ul>
              <li>AI-generated content is provided as a study aid and may contain errors</li>
              <li>AI content should not be submitted as original academic work</li>
              <li>We do not guarantee the accuracy or completeness of AI-generated materials</li>
              <li>You are responsible for verifying AI-generated content before relying on it</li>
            </ul>
          </section>

          <section>
            <h2>7. Intellectual Property</h2>
            <p>
              The Service, including its design, code, and branding, is owned by EMAI.
              Content you upload or create within ClassBridge remains yours. By using
              the Service, you grant us a limited license to process your content
              solely to provide the Service (e.g., sending it to OpenAI for study
              material generation).
            </p>
          </section>

          <section>
            <h2>8. Availability and Modifications</h2>
            <ul>
              <li>We strive to maintain Service availability but do not guarantee uninterrupted access</li>
              <li>We may modify, suspend, or discontinue features with reasonable notice</li>
              <li>Scheduled maintenance will be communicated in advance when possible</li>
              <li>We are not liable for any loss resulting from Service downtime</li>
            </ul>
          </section>

          <section>
            <h2>9. Limitation of Liability</h2>
            <p>
              To the maximum extent permitted by law, ClassBridge and EMAI shall not
              be liable for any indirect, incidental, special, or consequential
              damages arising from your use of the Service, including but not limited
              to loss of data, academic performance outcomes, or reliance on
              AI-generated content.
            </p>
            <p>
              The Service is provided "as is" and "as available" without warranties
              of any kind, whether express or implied.
            </p>
          </section>

          <section>
            <h2>10. Termination</h2>
            <p>
              We may suspend or terminate your access to the Service if you violate
              these Terms. You may delete your account at any time. Upon termination,
              your right to use the Service ceases immediately. Data deletion follows
              the timeline described in our <Link to="/privacy">Privacy Policy</Link>.
            </p>
          </section>

          <section>
            <h2>11. Governing Law</h2>
            <p>
              These Terms are governed by the laws of the Province of Ontario, Canada,
              without regard to conflict of law principles. Any disputes arising from
              these Terms shall be resolved in the courts of Ontario.
            </p>
          </section>

          <section>
            <h2>12. Changes to These Terms</h2>
            <p>
              We may update these Terms from time to time. Material changes will be
              communicated via email or a notice on the Service. Continued use of
              ClassBridge after changes are posted constitutes acceptance of the
              updated Terms.
            </p>
          </section>

          <section>
            <h2>13. Contact Us</h2>
            <p>
              If you have questions about these Terms, contact us at:
            </p>
            <p>
              <strong>Email:</strong> support@classbridge.ca<br />
              <strong>Project:</strong> ClassBridge by EMAI
            </p>
          </section>
        </div>

        <div className="legal-footer">
          <Link to="/privacy">Privacy Policy</Link>
          <span className="legal-divider">|</span>
          <Link to="/login">Back to Sign In</Link>
        </div>
      </div>
    </div>
  );
}
