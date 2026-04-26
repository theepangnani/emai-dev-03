import { useEffect, useRef, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { DashboardLayout } from '../../components/DashboardLayout';
import { ChildSelectorTabs } from '../../components/ChildSelectorTabs';
import { parentApi, type ChildSummary } from '../../api/parent';
import { EveningSummaryHero } from '../../components/dci/EveningSummaryHero';
import { DeadlineChip } from '../../components/dci/DeadlineChip';
import { ArtifactStrip } from '../../components/dci/ArtifactStrip';
import {
  useDciSummary,
  useConversationStarterFeedback,
} from '../../hooks/useDciSummary';
import { useDciConsent } from '../../hooks/useDciConsent';
import type { DciArtifact } from '../../api/dciSummary';
import { trackDciTelemetry } from '../../utils/dciTelemetry';
import { logger } from '../../utils/logger';
import './EveningSummaryPage.css';

/**
 * Format the current local date as yyyy-mm-dd. Pulled out so the
 * midnight-recompute effect (S-2 / #4215) and the initial value share
 * a single source of truth.
 */
function todayLocal(): string {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

/**
 * CB-DCI-001 M0-10 — Parent evening summary at /parent/today.
 *
 * Spec § 8. Reuses DashboardLayout + ChildSelectorTabs. Renders the new
 * EveningSummaryHero, deadline chips, conversation-starter card, and
 * tap-to-deep-dive artifact strip. Three lifecycle states: loading
 * (shimmer), no-checkin-today (empty), first-30-days (pattern stub).
 *
 * Telemetry: emits dci.parent.summary_viewed once per (kidId, date) pair,
 * plus starter_used / starter_regenerated / deep_dive_opened on action.
 */
export function EveningSummaryPage() {
  const navigate = useNavigate();
  // `null` means "no explicit choice yet" — the page derives the effective
  // selection from the children list (first kid wins) until the parent
  // taps a tab. We avoid setState-in-effect (project lint rule) by deriving
  // the value during render rather than syncing it back into state.
  const [explicitlySelectedKidId, setExplicitlySelectedKidId] = useState<
    number | null
  >(null);

  // S-2 (#4215): recompute `today` past midnight. Without this, parents who
  // leave the tab open across midnight see yesterday's date in chips and
  // queries. We refresh on focus + on a 60s interval — both cheap.
  const [today, setToday] = useState<string>(() => todayLocal());
  useEffect(() => {
    const tick = () => {
      const fresh = todayLocal();
      setToday((prev) => (prev === fresh ? prev : fresh));
    };
    const id = window.setInterval(tick, 60_000);
    window.addEventListener('focus', tick);
    return () => {
      window.clearInterval(id);
      window.removeEventListener('focus', tick);
    };
  }, []);

  // S-4 (#4217): TanStack Query for children — caches across the session,
  // dedupes against other consumers (e.g. dashboard), and gives us a clean
  // refetch handle for the Retry button (S-7 / #4220).
  const childrenQuery = useQuery<ChildSummary[]>({
    queryKey: ['parent', 'children'],
    queryFn: () => parentApi.getChildren(),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const children = childrenQuery.data ?? [];
  const childrenLoading = childrenQuery.isLoading;
  const childrenError = childrenQuery.isError;

  // Effective selection: parent's explicit pick, else first kid in the
  // list. Derived during render to avoid the cascading-render lint rule
  // that bans `setState` inside `useEffect`.
  const selectedKidId =
    explicitlySelectedKidId ??
    (children.length > 0 ? children[0].student_id : null);
  const setSelectedKidId = setExplicitlySelectedKidId;

  // M0-13 (#4260): gate the page on per-kid consent. If the consent row is
  // missing (404) or AI processing is off, bounce the parent to /dci/consent
  // with a return_to so they land back here after granting. The settings
  // flow (DciSettingsSection in AccountSettingsPage) remains an alternate
  // entry — both paths still work.
  const consentQuery = useDciConsent(selectedKidId);
  const consentMissing =
    selectedKidId !== null &&
    !consentQuery.isLoading &&
    (consentQuery.isError || (consentQuery.data && !consentQuery.data.ai_ok));
  useEffect(() => {
    if (!consentMissing) return;
    const target = `/dci/consent?return_to=${encodeURIComponent('/parent/today')}`;
    navigate(target, { replace: true });
  }, [consentMissing, navigate]);

  // #4268: only fetch the summary once consent is confirmed present. Without
  // this gate the summary endpoint fires in parallel with the consent check
  // and 403s on every redirect-bound visit, wasting one backend cycle (and
  // an OpenAI call when the daily summary is uncached).
  const consentReady =
    selectedKidId !== null &&
    !consentQuery.isLoading &&
    !consentQuery.isError &&
    consentQuery.data?.ai_ok === true;
  const summaryQuery = useDciSummary(consentReady ? selectedKidId : null, today);
  const feedbackMutation = useConversationStarterFeedback();

  const summary = summaryQuery.data?.summary ?? null;
  const state = summaryQuery.data?.state ?? null;

  // I-2: log when the backend returns a `(state, summary)` pair we don't
  // expect — e.g. state='ready' with a null summary. Helps catch contract
  // drift during the M0 ramp without breaking the page.
  useEffect(() => {
    if (!summaryQuery.data) return;
    const expectsSummary = state === 'ready';
    if (expectsSummary && !summary) {
      logger.warn('dci.summary.state_mismatch', {
        state,
        hasSummary: !!summary,
      });
    }
  }, [summaryQuery.data, state, summary]);

  // Fire summary_viewed once per (kidId, date) when a real summary loads.
  // useRef avoids the cascading-render lint rule that bans setState in
  // effects — we only need to remember the last-seen key, not re-render.
  const seenKeyRef = useRef<string | null>(null);
  useEffect(() => {
    if (!summary || !selectedKidId) return;
    const key = `${selectedKidId}:${summary.summary_date}`;
    if (seenKeyRef.current === key) return;
    seenKeyRef.current = key;
    trackDciTelemetry('dci.parent.summary_viewed', {
      kid_id: selectedKidId,
      date: summary.summary_date,
      summary_id: summary.id,
    });
  }, [summary, selectedKidId]);

  const selectedChild = children.find((c) => c.student_id === selectedKidId) ?? null;

  const handleStarterUsedToggle = useCallback(() => {
    if (!summary?.conversation_starter || !selectedKidId) return;
    const starter = summary.conversation_starter;
    // S-5 (#4218): clicking an already-used starter is an explicit untoggle.
    // We send `'undo_used'` so the backend can clear `was_used`. Clicking
    // an un-used starter still sends `'thumbs_up'`.
    const nextValue = !starter.was_used;
    trackDciTelemetry('dci.parent.starter_used', {
      kid_id: selectedKidId,
      starter_id: starter.id,
      next_value: nextValue,
    });
    feedbackMutation.mutate({
      starterId: starter.id,
      feedback: nextValue ? 'thumbs_up' : 'undo_used',
      kidId: selectedKidId,
      date: today,
    });
  }, [summary, selectedKidId, today, feedbackMutation]);

  const handleStarterRegenerate = useCallback(() => {
    if (!summary?.conversation_starter || !selectedKidId) return;
    const starter = summary.conversation_starter;
    trackDciTelemetry('dci.parent.starter_regenerated', {
      kid_id: selectedKidId,
      starter_id: starter.id,
    });
    feedbackMutation.mutate({
      starterId: starter.id,
      feedback: 'regenerate',
      kidId: selectedKidId,
      date: today,
    });
  }, [summary, selectedKidId, today, feedbackMutation]);

  const handleArtifactOpen = useCallback(
    (artifact: DciArtifact) => {
      trackDciTelemetry('dci.parent.deep_dive_opened', {
        kid_id: selectedKidId,
        artifact_id: artifact.id,
        artifact_type: artifact.artifact_type,
      });
    },
    [selectedKidId],
  );

  return (
    <DashboardLayout welcomeSubtitle="Tonight's check-in summary">
      <div className="dci-evening-page">
        {children.length > 0 && (
          <div className="dci-evening-page__tabs">
            <ChildSelectorTabs
              children={children}
              selectedChild={selectedKidId}
              onSelectChild={(id) => {
                if (id != null) setSelectedKidId(id);
              }}
            />
          </div>
        )}

        {childrenLoading ? (
          <SummaryShimmer />
        ) : childrenError ? (
          // S-7 (#4220): Retry button so a transient network failure
          // doesn't force a full page reload.
          <EmptyState
            title="We couldn't load your kids"
            body="Try refreshing in a moment. If this keeps happening, please contact support."
            action={{
              label: 'Retry',
              onClick: () => childrenQuery.refetch(),
              disabled: childrenQuery.isFetching,
            }}
          />
        ) : children.length === 0 ? (
          <EmptyState
            title="No kids linked yet"
            body="Add a child from My Kids to start seeing evening check-ins."
          />
        ) : summaryQuery.isLoading ? (
          <SummaryShimmer />
        ) : summaryQuery.isError ? (
          <EmptyState
            title="We couldn't load tonight's summary"
            body="Try again in a moment. If this keeps happening, your DCI feature flag may be off."
          />
        ) : state === 'no_checkin_today' ? (
          <EmptyState
            title={`${selectedChild?.full_name ?? 'Your kid'} hasn't checked in yet today`}
            body="That's okay — some days don't have a check-in. Tomorrow you'll see a fresh 30-second read."
          />
        ) : state === 'first_30_days' ? (
          <EmptyState
            title="We're learning about your kid"
            body="Check back in 30 days for your first weekly insight."
          />
        ) : summary ? (
          <>
            <EveningSummaryHero
              kidName={summary.kid_name}
              date={summary.summary_date}
              bullets={summary.bullets}
            />

            {summary.upcoming.length > 0 && (
              <section
                className="dci-evening-page__upcoming"
                aria-label="Upcoming deadlines"
              >
                <h3 className="dci-evening-page__section-title">Upcoming</h3>
                <div className="dci-evening-page__chips">
                  {summary.upcoming.map((chip) => (
                    <DeadlineChip key={chip.id} chip={chip} />
                  ))}
                </div>
              </section>
            )}

            {summary.conversation_starter && (
              <ConversationStarterCard
                text={summary.conversation_starter.text}
                wasUsed={!!summary.conversation_starter.was_used}
                onToggleUsed={handleStarterUsedToggle}
                onRegenerate={handleStarterRegenerate}
                disabled={feedbackMutation.isPending}
                /* S-6 (#4219): inline Retry surfaces if the toast is missed. */
                hasError={feedbackMutation.isError}
                onRetry={feedbackMutation.retry}
              />
            )}

            <ArtifactStrip
              artifacts={summary.artifacts}
              onOpen={handleArtifactOpen}
            />
          </>
        ) : (
          <EmptyState
            title="Nothing to show yet"
            body="Try refreshing in a moment."
          />
        )}
      </div>
    </DashboardLayout>
  );
}

interface ConversationStarterCardProps {
  text: string;
  wasUsed: boolean;
  onToggleUsed: () => void;
  onRegenerate: () => void;
  disabled?: boolean;
  hasError?: boolean;
  onRetry?: () => void;
}

function ConversationStarterCard({
  text,
  wasUsed,
  onToggleUsed,
  onRegenerate,
  disabled,
  hasError,
  onRetry,
}: ConversationStarterCardProps) {
  return (
    <section
      className="dci-conv-starter"
      aria-labelledby="dci-conv-starter-title"
    >
      <header className="dci-conv-starter__header">
        <h3
          className="dci-conv-starter__title"
          id="dci-conv-starter-title"
        >
          Tonight&rsquo;s conversation starter
        </h3>
      </header>
      <p className="dci-conv-starter__text">{text}</p>
      <footer className="dci-conv-starter__footer">
        <button
          type="button"
          className={`dci-conv-starter__used${wasUsed ? ' dci-conv-starter__used--on' : ''}`}
          onClick={onToggleUsed}
          aria-pressed={wasUsed}
          disabled={disabled}
        >
          {wasUsed ? '✓ I used this' : 'I used this'}
        </button>
        <button
          type="button"
          className="dci-conv-starter__regen"
          onClick={onRegenerate}
          disabled={disabled}
        >
          Regenerate
        </button>
      </footer>
      {hasError && (
        <div className="dci-conv-starter__error" role="alert">
          <span className="dci-conv-starter__error-text">
            Couldn&rsquo;t save your choice.
          </span>
          {onRetry && (
            <button
              type="button"
              className="dci-conv-starter__retry"
              onClick={onRetry}
              disabled={disabled}
            >
              Retry
            </button>
          )}
        </div>
      )}
    </section>
  );
}

function SummaryShimmer() {
  return (
    <div
      className="dci-evening-page__shimmer"
      role="status"
      aria-label="Loading tonight's summary"
    >
      <div className="dci-shimmer-line dci-shimmer-line--hero" />
      <div className="dci-shimmer-line" />
      <div className="dci-shimmer-line" />
      <div className="dci-shimmer-line" />
      <div className="dci-shimmer-line dci-shimmer-line--card" />
    </div>
  );
}

interface EmptyStateProps {
  title: string;
  body: string;
  /** Optional CTA — used by the children-load error state's Retry (S-7). */
  action?: {
    label: string;
    onClick: () => void;
    disabled?: boolean;
  };
}

function EmptyState({ title, body, action }: EmptyStateProps) {
  return (
    <section className="dci-evening-page__empty" role="status">
      <h3 className="dci-evening-page__empty-title">{title}</h3>
      <p className="dci-evening-page__empty-body">{body}</p>
      {action && (
        <button
          type="button"
          className="dci-evening-page__empty-action"
          onClick={action.onClick}
          disabled={action.disabled}
        >
          {action.label}
        </button>
      )}
    </section>
  );
}
