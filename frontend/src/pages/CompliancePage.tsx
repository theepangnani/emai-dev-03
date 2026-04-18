import { Link } from 'react-router-dom';
import './CompliancePage.css';

// SUGGESTION: automate this via build-time env var or latest-deploy timestamp.
const LAST_UPDATED = '2026-04-18';

const SECTIONS = [
  { id: 'hosting', title: 'Hosted in Canada (GCP Toronto)' },
  { id: 'mfippa', title: 'MFIPPA-aligned' },
  { id: 'pipeda', title: 'PIPEDA-compliant (self-attested)' },
  { id: 'stack', title: 'Canadian-hosted stack' },
];

export function CompliancePage() {
  return (
    <div className="compliance-page">
      <article className="compliance-card">
        <header className="compliance-header">
          <Link to="/" className="compliance-brand" aria-label="ClassBridge home">
            <img src="/classbridge-logo.png" alt="" className="compliance-logo" />
            <span>ClassBridge</span>
          </Link>
          <h1>How ClassBridge handles your family&rsquo;s data</h1>
          <p className="compliance-subtitle">
            Plain-language answers to the compliance badges you see across the site.
            We&rsquo;ve kept the hedging honest: where we&rsquo;re aligned but not certified,
            we say so.
          </p>
          <p className="compliance-meta">Last updated: {LAST_UPDATED}</p>
        </header>

        <nav className="compliance-toc" aria-label="On this page">
          <h2>On this page</h2>
          <ul>
            {SECTIONS.map((s) => (
              <li key={s.id}>
                <a href={`#${s.id}`}>{s.title}</a>
              </li>
            ))}
          </ul>
        </nav>

        <section id="hosting" className="compliance-section">
          <h2>Hosted in Canada (GCP Toronto)</h2>
          <p>
            Our application servers and main database run in Google Cloud&rsquo;s
            Toronto region (<code>northamerica-northeast2</code>). That means the
            computers that store and process your data sit on Canadian soil, under
            Canadian jurisdiction, rather than being routed through data centres
            in the US or abroad.
          </p>
          <p>
            This covers the ClassBridge web app (Cloud Run) and our primary
            PostgreSQL database (Cloud SQL). Backups and file storage buckets are
            configured to stay in the same region.
          </p>
          <p className="compliance-caveat">
            A small number of sub-processors (for example, AI providers we use to
            generate study materials) operate outside Canada. See the
            <a href="#stack"> Canadian-hosted stack </a>
            section below for detail on where each vendor sits.
          </p>
        </section>

        <section id="mfippa" className="compliance-section">
          <h2>MFIPPA-aligned</h2>
          <p>
            Ontario&rsquo;s Municipal Freedom of Information and Protection of
            Privacy Act (MFIPPA) governs how school boards collect and handle
            personal information. ClassBridge is built so that when a board or
            school uses it, the data handling lines up with MFIPPA principles:
            collecting only what&rsquo;s needed, limiting access by role, logging
            who sees what, and keeping data in Canada.
          </p>
          <p>
            Concretely, this includes role-based access controls for parents,
            students, teachers, and admins; audit logs of sensitive actions;
            data-minimisation in what we ask you to enter; and Canadian-only
            data residency for the primary database.
          </p>
          <p className="compliance-caveat">
            <strong>A note on language:</strong> we say &ldquo;MFIPPA-aligned,&rdquo;
            not &ldquo;MFIPPA-certified.&rdquo; There is no public certification
            program for MFIPPA &mdash; it&rsquo;s a statute, not a badge. Alignment
            means we&rsquo;ve mapped our practices to the Act&rsquo;s requirements
            as they apply to school boards. The detailed mapping lives in our
            internal DTAP/VASP compliance report, shared with boards during
            procurement review.
          </p>
        </section>

        <section id="pipeda" className="compliance-section">
          <h2>PIPEDA-compliant (self-attested)</h2>
          <p>
            Canada&rsquo;s Personal Information Protection and Electronic
            Documents Act (PIPEDA) sets out ten fair-information principles for
            how private-sector organisations handle personal data. Our privacy
            program is built around those principles:
          </p>
          <ul>
            <li>We tell you what we collect and why (<Link to="/privacy">privacy policy</Link>).</li>
            <li>We ask for consent before connecting third-party services like Google Classroom.</li>
            <li>We collect only what&rsquo;s needed to run the service.</li>
            <li>You can access, correct, export, or delete your data at any time.</li>
            <li>We have a documented breach-notification process.</li>
            <li>Data is retained only as long as your account is active, then removed on request.</li>
          </ul>
          <p className="compliance-caveat">
            <strong>Self-attested:</strong> PIPEDA is enforced by the Office of
            the Privacy Commissioner of Canada, but there is no government
            &ldquo;PIPEDA certificate&rdquo; to apply for. Compliance is
            self-assessed by each organisation. We&rsquo;ve done that assessment
            internally and the results back the claim on this page. If you
            believe we&rsquo;ve fallen short, email
            <a href="mailto:privacy@classbridge.ca"> privacy@classbridge.ca</a>.
          </p>
        </section>

        <section id="stack" className="compliance-section">
          <h2>Canadian-hosted stack</h2>
          <p>
            ClassBridge Inc. is incorporated in Ontario, and we choose Canadian
            regions for our infrastructure wherever that&rsquo;s configurable:
          </p>
          <ul>
            <li><strong>Application &amp; database:</strong> Google Cloud, Toronto region.</li>
            <li><strong>SMS / WhatsApp:</strong> Twilio, using a Canadian long-code (+1 647-800-8533).</li>
            <li><strong>Transactional email:</strong> SendGrid, under a sub-processor agreement.</li>
          </ul>
          <p className="compliance-caveat">
            &ldquo;Canadian-hosted stack&rdquo; describes where our core
            infrastructure runs &mdash; not a claim that every sub-processor is
            Canadian. A few services don&rsquo;t offer Canadian regions: our AI
            providers (used to generate study guides, quizzes, and flashcards)
            process content in the US, and SendGrid uses global relays to
            deliver email. We disclose these in our
            <Link to="/privacy"> privacy policy</Link> and keep the list current.
          </p>
        </section>

        <footer className="compliance-footer">
          <p>
            Questions? Email
            <a href="mailto:privacy@classbridge.ca"> privacy@classbridge.ca</a>,
            or read our full <Link to="/privacy">privacy policy</Link> and
            <Link to="/terms"> terms of service</Link>.
          </p>
          <p>
            <Link to="/">&larr; Back to ClassBridge</Link>
          </p>
        </footer>
      </article>
    </div>
  );
}
