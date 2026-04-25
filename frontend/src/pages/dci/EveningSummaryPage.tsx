import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
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
import type { DciArtifact } from '../../api/dciSummary';
import { trackDciTelemetry } from '../../utils/dciTelemetry';
import './EveningSummaryPage.css';

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
  const [children, setChildren] = useState<ChildSummary[]>([]);
  const [selectedKidId, setSelectedKidId] = useState<number | null>(null);
  const [childrenLoading, setChildrenLoading] = useState(true);

  // Today, in local time, formatted yyyy-mm-dd. M0 only renders today —
  // historical days are a fast-follow.
  const today = useMemo(() => {
    const d = new Date();
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
  }, []);

  useEffect(() => {
    let cancelled = false;
    parentApi
      .getChildren()
      .then((kids) => {
        if (cancelled) return;
        setChildren(kids);
        if (kids.length > 0) {
          setSelectedKidId(kids[0].student_id);
        }
      })
      .catch(() => {
        // Empty children list will surface the empty state below.
      })
      .finally(() => {
        if (!cancelled) setChildrenLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const summaryQuery = useDciSummary(selectedKidId, today);
  const feedbackMutation = useConversationStarterFeedback();

  const summary = summaryQuery.data?.summary ?? null;
  const state = summaryQuery.data?.state ?? null;

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
    trackDciTelemetry('dci.parent.starter_used', {
      kid_id: selectedKidId,
      starter_id: starter.id,
      next_value: !starter.was_used,
    });
    feedbackMutation.mutate({
      starterId: starter.id,
      feedback: 'thumbs_up',
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
              />
            )}

            <ArtifactStrip
              artifacts={summary.artifacts}
              onOpen={handleArtifactOpen}
            />

            {/* First-30-days pattern stub at the bottom (single line) */}
            <p className="dci-evening-page__pattern-stub">
              We&rsquo;re learning about {summary.kid_name}. Check back in 30 days
              for your first insight.
            </p>
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
}

function ConversationStarterCard({
  text,
  wasUsed,
  onToggleUsed,
  onRegenerate,
  disabled,
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

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <section className="dci-evening-page__empty" role="status">
      <h3 className="dci-evening-page__empty-title">{title}</h3>
      <p className="dci-evening-page__empty-body">{body}</p>
    </section>
  );
}
