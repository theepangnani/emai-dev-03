import { useState, useCallback } from 'react';
import './EmailForwardSetup.css';

interface EmailForwardSetupProps {
  userEmail: string;
  userId: number;
  onDone?: () => void;
}

export default function EmailForwardSetup({ userEmail, userId, onDone }: EmailForwardSetupProps) {
  const [copied, setCopied] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<'success' | 'none' | null>(null);

  const forwardingAddress = `import+${userId}@classbridge.app`;

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(forwardingAddress);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement('textarea');
      textarea.value = forwardingAddress;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [forwardingAddress]);

  const handleTest = useCallback(async () => {
    setTesting(true);
    setTestResult(null);
    // Simulate a status check — in production this would call an API endpoint
    // e.g. GET /api/email-import/status?userId={userId}
    await new Promise(resolve => setTimeout(resolve, 1500));
    setTestResult('none');
    setTesting(false);
  }, []);

  return (
    <div className="email-forward-setup">
      {/* ── Header ──────────────────────────────────────────── */}
      <div className="efs-header">
        <h1 className="efs-header__title">Email Forward Setup</h1>
        <p className="efs-header__desc">
          Automatically import assignments and announcements by forwarding
          Google Classroom emails.
        </p>
      </div>

      {/* ── Forwarding Address Card ─────────────────────────── */}
      <div className="efs-card efs-address-card">
        <h2 className="efs-card__title">
          <span className="efs-card__title-icon" aria-hidden="true">&#9993;</span>
          Your Forwarding Address
        </h2>
        <div className="efs-address-box">
          <span className="efs-address-text" aria-label="Forwarding email address">
            {forwardingAddress}
          </span>
          <button
            className={`efs-copy-btn ${copied ? 'efs-copy-btn--copied' : ''}`}
            onClick={handleCopy}
            aria-label={copied ? 'Copied to clipboard' : 'Copy forwarding address'}
          >
            {copied ? (
              <>&#10003; Copied!</>
            ) : (
              <>&#128203; Copy</>
            )}
          </button>
        </div>
        {copied && (
          <p
            style={{
              margin: '8px 0 0',
              fontSize: '13px',
              color: 'var(--color-success)',
              fontWeight: 600,
            }}
            role="status"
          >
            Copied to clipboard!
          </p>
        )}
      </div>

      {/* ── Setup Instructions ──────────────────────────────── */}
      <div className="efs-card">
        <h2 className="efs-card__title">
          <span className="efs-card__title-icon" aria-hidden="true">&#128221;</span>
          Setup Instructions
        </h2>
        <ol className="efs-steps">
          {/* Step 1 */}
          <li className="efs-step">
            <div className="efs-step__number" aria-hidden="true">1</div>
            <div className="efs-step__body">
              <h3 className="efs-step__title">Open Gmail Settings</h3>
              <p className="efs-step__desc">
                Go to Gmail and click the gear icon in the top right corner.
                Select <strong>See all settings</strong>, then navigate to the{' '}
                <strong>Filters and Blocked Addresses</strong> tab.
              </p>
            </div>
          </li>

          {/* Step 2 */}
          <li className="efs-step">
            <div className="efs-step__number" aria-hidden="true">2</div>
            <div className="efs-step__body">
              <h3 className="efs-step__title">Create a new filter</h3>
              <p className="efs-step__desc">
                Click <strong>Create a new filter</strong>. In the{' '}
                <strong>From</strong> field, enter:{' '}
                <code>classroom.google.com</code>
              </p>
              <div className="efs-step__substep">
                <span className="efs-step__substep-icon" aria-hidden="true">&#8594;</span>
                <span>Click <strong>Create filter</strong> to continue.</span>
              </div>
            </div>
          </li>

          {/* Step 3 */}
          <li className="efs-step">
            <div className="efs-step__number" aria-hidden="true">3</div>
            <div className="efs-step__body">
              <h3 className="efs-step__title">Set up forwarding</h3>
              <p className="efs-step__desc">
                Check <strong>Forward it to:</strong> and paste your ClassBridge
                forwarding address shown above.
              </p>
              <div className="efs-step__substep">
                <span className="efs-step__substep-icon" aria-hidden="true">&#10003;</span>
                <span>
                  Also check <strong>Keep Gmail's copy in the Inbox</strong> so
                  you still see emails in Gmail.
                </span>
              </div>
              <div className="efs-step__substep">
                <span className="efs-step__substep-icon" aria-hidden="true">&#8594;</span>
                <span>Click <strong>Create filter</strong> to finish.</span>
              </div>
            </div>
          </li>

          {/* Step 4 */}
          <li className="efs-step">
            <div className="efs-step__number" aria-hidden="true">4</div>
            <div className="efs-step__body">
              <h3 className="efs-step__title">Confirm forwarding</h3>
              <p className="efs-step__desc">
                Gmail will send a confirmation email to your forwarding address.
                ClassBridge will automatically verify it &mdash; no action
                needed on your end.
              </p>
            </div>
          </li>
        </ol>
      </div>

      {/* ── What Gets Imported ──────────────────────────────── */}
      <div className="efs-card">
        <h2 className="efs-card__title">
          <span className="efs-card__title-icon" aria-hidden="true">&#128230;</span>
          What Gets Imported
        </h2>
        <div className="efs-imports-grid">
          <div className="efs-import-item">
            <div className="efs-import-item__icon efs-import-item__icon--assignments" aria-hidden="true">
              &#128196;
            </div>
            <div className="efs-import-item__text">
              <p className="efs-import-item__label">Assignment notifications</p>
              <p className="efs-import-item__desc">New assignments with due dates</p>
            </div>
          </div>

          <div className="efs-import-item">
            <div className="efs-import-item__icon efs-import-item__icon--summaries" aria-hidden="true">
              &#128202;
            </div>
            <div className="efs-import-item__text">
              <p className="efs-import-item__label">Guardian summaries</p>
              <p className="efs-import-item__desc">Weekly digest of all assignments</p>
            </div>
          </div>

          <div className="efs-import-item">
            <div className="efs-import-item__icon efs-import-item__icon--grades" aria-hidden="true">
              &#11088;
            </div>
            <div className="efs-import-item__text">
              <p className="efs-import-item__label">Grade notifications</p>
              <p className="efs-import-item__desc">Score updates</p>
            </div>
          </div>

          <div className="efs-import-item">
            <div className="efs-import-item__icon efs-import-item__icon--announcements" aria-hidden="true">
              &#128227;
            </div>
            <div className="efs-import-item__text">
              <p className="efs-import-item__label">Announcements</p>
              <p className="efs-import-item__desc">Teacher posts</p>
            </div>
          </div>
        </div>
      </div>

      {/* ── Status Section ──────────────────────────────────── */}
      <div className="efs-card">
        <h2 className="efs-card__title">
          <span className="efs-card__title-icon" aria-hidden="true">&#128225;</span>
          Forwarding Status
        </h2>
        <div className="efs-status">
          <div className="efs-status__info">
            <span
              className={`efs-status__dot ${
                testResult === 'success'
                  ? 'efs-status__dot--active'
                  : 'efs-status__dot--waiting'
              }`}
              aria-hidden="true"
            />
            <span
              className={`efs-status__text ${
                testResult === 'success' ? 'efs-status__text--active' : ''
              }`}
            >
              {testResult === 'success'
                ? 'Forwarding is active!'
                : testResult === 'none'
                  ? 'No emails received yet'
                  : 'Waiting for first forwarded email...'}
            </span>
          </div>
          <button
            className="efs-test-btn"
            onClick={handleTest}
            disabled={testing}
            aria-label="Test if forwarding is working"
          >
            {testing ? (
              <>Checking...</>
            ) : (
              <>&#128269; Test</>
            )}
          </button>
        </div>
      </div>

      {/* ── Done Button ─────────────────────────────────────── */}
      {onDone && (
        <div className="efs-done-row">
          <button className="efs-done-btn" onClick={onDone}>
            Done
          </button>
        </div>
      )}
    </div>
  );
}
