/**
 * CB-CMCP-001 M1-F 1F-4 (#4498) — Parent Companion 5-section render page.
 *
 * Renders the 5-section ``ParentCompanionContent`` produced by the 1F-2
 * service (`ParentCompanionService.generate_5_section`). Sections per FR-02.6:
 *
 *   1. SE explanation                       (2 sentences, plain language)
 *   2. Talking points                       (3-5 conversation starters)
 *   3. Coaching prompts                     (open-ended questions)
 *   4. How to help without giving the answer (paragraph)
 *   5. Bridge deep-link payload             (CTA back into Bridge)
 *
 * Visual treatment is *distinct* from student-facing artifacts (warm coaching
 * tone, NOT Arc-led) — but reuses the Bridge token system. Bridge tokens
 * only — no new tokens introduced (per locked-plan §6).
 *
 * Route: ``/parent/companion/:artifact_id`` — gated to PARENT role via
 * ProtectedRoute in App.tsx. The page handles loading/error/empty states.
 */
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { DashboardLayout } from '../../components/DashboardLayout';
import {
  cmcpParentCompanionApi,
  type ParentCompanionContent,
} from '../../api/cmcpParentCompanion';
import './ParentCompanionPage.css';

type LoadState = 'loading' | 'ready' | 'error' | 'empty';

interface ErrorShape {
  status?: number;
  message: string;
}

function extractError(err: unknown): ErrorShape {
  const e = err as {
    response?: { status?: number; data?: { detail?: string } };
    message?: string;
  };
  const status = e?.response?.status;
  const detail = e?.response?.data?.detail;
  const message = detail || e?.message || 'Something went wrong.';
  return { status, message };
}

/**
 * Empty content guard — if all five sections are empty / blank we treat the
 * artifact as empty rather than showing an awkward shell. This keeps the page
 * resilient to a 200-with-stub-payload response shape during 1F-3 ramp.
 */
function isEmptyContent(content: ParentCompanionContent): boolean {
  const hasExplanation = !!content.se_explanation?.trim();
  const hasTalking = (content.talking_points || []).some((t) => !!t?.trim());
  const hasPrompts = (content.coaching_prompts || []).some(
    (p) => !!p?.trim(),
  );
  const hasHowTo = !!content.how_to_help_without_giving_answer?.trim();
  return !hasExplanation && !hasTalking && !hasPrompts && !hasHowTo;
}

function LoadingState() {
  return (
    <div
      className="parent-companion-state"
      role="status"
      aria-live="polite"
      data-testid="parent-companion-loading"
    >
      <h2 className="parent-companion-state-title">Loading companion…</h2>
      <div className="parent-companion-skeleton-row" />
      <div className="parent-companion-skeleton-row" />
      <div className="parent-companion-skeleton-row" />
    </div>
  );
}

function ErrorState({ error }: { error: ErrorShape }) {
  let title = 'Something went wrong';
  let body = error.message;
  if (error.status === 404) {
    title = 'Companion not found';
    body =
      "We couldn't find a Parent Companion for this artifact. It may have been removed, or it hasn't been generated yet.";
  } else if (error.status === 403) {
    title = "You don't have access";
    body =
      "This Parent Companion belongs to a different family. If you think this is wrong, reach out to support.";
  } else if (error.status === 401) {
    title = 'Please sign in again';
    body = 'Your session has expired. Sign in to view the companion.';
  }
  return (
    <div
      className="parent-companion-state parent-companion-state--error"
      role="alert"
      data-testid="parent-companion-error"
    >
      <h2 className="parent-companion-state-title">{title}</h2>
      <p className="parent-companion-state-body">{body}</p>
    </div>
  );
}

function EmptyState() {
  return (
    <div
      className="parent-companion-state"
      role="status"
      data-testid="parent-companion-empty"
    >
      <h2 className="parent-companion-state-title">Nothing to show yet</h2>
      <p className="parent-companion-state-body">
        Your child's companion will appear here once it's generated.
      </p>
    </div>
  );
}

interface DeepLinkCTAProps {
  payload: ParentCompanionContent['bridge_deep_link_payload'];
}

function DeepLinkCTA({ payload }: DeepLinkCTAProps) {
  const target = payload?.deep_link_target?.trim() || null;
  const summary = payload?.week_summary?.trim() || null;

  return (
    <section
      className="parent-companion-section parent-companion-deeplink"
      data-testid="parent-companion-deeplink"
    >
      <span className="parent-companion-section-kicker">Open in Bridge</span>
      <h3 className="parent-companion-section-title">
        Continue with your child
      </h3>
      {summary ? (
        <p className="parent-companion-deeplink-summary">{summary}</p>
      ) : null}
      {target ? (
        <Link
          className="parent-companion-deeplink-button"
          to={target}
          data-testid="parent-companion-deeplink-link"
        >
          Open in Bridge
          <span aria-hidden="true" className="parent-companion-deeplink-arrow">
            →
          </span>
        </Link>
      ) : (
        <button
          type="button"
          className="parent-companion-deeplink-button"
          disabled
          data-testid="parent-companion-deeplink-disabled"
        >
          Bridge link coming soon
        </button>
      )}
    </section>
  );
}

interface CompanionBodyProps {
  content: ParentCompanionContent;
}

function CompanionBody({ content }: CompanionBodyProps) {
  const weekSummary = content.bridge_deep_link_payload?.week_summary?.trim();

  return (
    <>
      <header
        className="parent-companion-header"
        data-testid="parent-companion-header"
      >
        <span className="parent-companion-kicker">Parent Companion</span>
        <h1 className="parent-companion-title">
          How to support your child this week
        </h1>
        {weekSummary ? (
          <span className="parent-companion-week">{weekSummary}</span>
        ) : null}
      </header>

      {/* Section 1 — SE explanation. */}
      <section
        className="parent-companion-section"
        data-testid="parent-companion-explanation"
      >
        <span className="parent-companion-section-kicker">
          What they're learning
        </span>
        <h2 className="parent-companion-section-title">
          The big idea, in plain language
        </h2>
        <p className="parent-companion-explanation">
          {content.se_explanation}
        </p>
      </section>

      {/* Section 2 — Talking points. */}
      {content.talking_points && content.talking_points.length > 0 ? (
        <section
          className="parent-companion-section"
          data-testid="parent-companion-talking-points"
        >
          <span className="parent-companion-section-kicker">
            At the dinner table
          </span>
          <h2 className="parent-companion-section-title">
            Talking points to start the conversation
          </h2>
          <ol className="parent-companion-talking-points">
            {content.talking_points.map((point, idx) => (
              <li key={`talking-${idx}`}>
                <span>{point}</span>
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      {/* Section 3 — Coaching prompts. */}
      {content.coaching_prompts && content.coaching_prompts.length > 0 ? (
        <section
          className="parent-companion-section"
          data-testid="parent-companion-prompts"
        >
          <span className="parent-companion-section-kicker">
            Coaching prompts
          </span>
          <h2 className="parent-companion-section-title">
            Open questions to check understanding
          </h2>
          <ul className="parent-companion-prompts">
            {content.coaching_prompts.map((prompt, idx) => (
              <li key={`prompt-${idx}`}>{prompt}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {/* Section 4 — How to help without giving the answer. */}
      <section
        className="parent-companion-section parent-companion-how-to-help"
        data-testid="parent-companion-how-to-help"
      >
        <span className="parent-companion-section-kicker">
          Coach, don't solve
        </span>
        <h2 className="parent-companion-section-title">
          How to help without giving the answer
        </h2>
        <p className="parent-companion-how-to-help-text">
          {content.how_to_help_without_giving_answer}
        </p>
      </section>

      {/* Section 5 — Bridge deep link. */}
      <DeepLinkCTA payload={content.bridge_deep_link_payload} />
    </>
  );
}

export function ParentCompanionPage() {
  const { artifact_id: artifactId } = useParams<{ artifact_id: string }>();
  // Initialize state derivation off `artifactId` synchronously so we never
  // call setState inside the effect for the missing-id branch (lint rule
  // `react-hooks/set-state-in-effect`).
  const missingId = !artifactId;
  const [state, setState] = useState<LoadState>(
    missingId ? 'error' : 'loading',
  );
  const [content, setContent] = useState<ParentCompanionContent | null>(null);
  const [error, setError] = useState<ErrorShape | null>(
    missingId ? { message: 'Missing artifact id in URL.' } : null,
  );

  useEffect(() => {
    if (!artifactId) {
      // No fetch to do — state was initialized to error above.
      return;
    }
    let cancelled = false;

    cmcpParentCompanionApi
      .get(artifactId)
      .then((data) => {
        if (cancelled) return;
        if (!data || isEmptyContent(data)) {
          setState('empty');
          setContent(data ?? null);
        } else {
          setContent(data);
          setState('ready');
        }
      })
      .catch((err) => {
        if (cancelled) return;
        setError(extractError(err));
        setState('error');
      });

    return () => {
      cancelled = true;
    };
  }, [artifactId]);

  return (
    <DashboardLayout welcomeSubtitle="Parent Companion">
      <div className="parent-companion-page" data-testid="parent-companion-page">
        {state === 'loading' && <LoadingState />}
        {state === 'error' && error && <ErrorState error={error} />}
        {state === 'empty' && <EmptyState />}
        {state === 'ready' && content && <CompanionBody content={content} />}
      </div>
    </DashboardLayout>
  );
}

export default ParentCompanionPage;
