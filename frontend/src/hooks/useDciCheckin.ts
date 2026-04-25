/**
 * useDciCheckin — submit + poll-until-classified flow for the kid /checkin
 * route. Pairs a TanStack Query mutation (submit) with a status poll that
 * keeps running until the backend marks the check-in `classified` (or
 * `failed`) so the AIDetectedChip can render ASAP.
 *
 * Polling cadence is intentionally short (250ms) because the design lock
 * gives the kid a ≤ 2s p50 budget for the chip — see
 * `docs/design/CB-DCI-001-daily-checkin.md` § 7 / § 12.
 */
import { useEffect, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
  dciApi,
  type DciCheckinCreateResponse,
  type DciCheckinStatusResponse,
  type DciClassification,
  type DciCorrectionPayload,
} from '../api/dci';

const POLL_INTERVAL_MS = 250;
const POLL_TIMEOUT_MS = 10_000;

interface UseDciCheckinResult {
  submit: (form: FormData) => void;
  isSubmitting: boolean;
  submitError: Error | null;
  checkinId: number | null;
  classifications: DciClassification[];
  status: DciCheckinStatusResponse['status'] | null;
  /** ms taken from submit -> classified (for `dci.kid.classify_ms`). */
  classifyMs: number | null;
  applyCorrection: (
    payload: DciCorrectionPayload,
  ) => Promise<DciClassification>;
  reset: () => void;
}

export function useDciCheckin(): UseDciCheckinResult {
  const [checkinId, setCheckinId] = useState<number | null>(null);
  const [submitStartedAt, setSubmitStartedAt] = useState<number | null>(null);
  const [classifyMs, setClassifyMs] = useState<number | null>(null);
  const [classifications, setClassifications] = useState<DciClassification[]>(
    [],
  );

  const submitMutation = useMutation<DciCheckinCreateResponse, Error, FormData>({
    mutationFn: (form: FormData) => dciApi.submitCheckin(form),
    onMutate: () => {
      setClassifyMs(null);
      setClassifications([]);
      setSubmitStartedAt(performance.now());
    },
    onSuccess: (data) => {
      setCheckinId(data.checkin_id);
      if (data.classifications && data.classifications.length > 0) {
        setClassifications(data.classifications);
        setClassifyMs(
          submitStartedAt !== null
            ? Math.round(performance.now() - submitStartedAt)
            : null,
        );
      }
    },
  });

  // Poll status until classified/failed or timeout. We stop refetching by
  // returning `false` from refetchInterval once we have a terminal state.
  const statusQuery = useQuery<DciCheckinStatusResponse>({
    queryKey: ['dci', 'checkin', checkinId, 'status'],
    queryFn: () => dciApi.getStatus(checkinId as number),
    enabled: checkinId !== null && classifyMs === null,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return POLL_INTERVAL_MS;
      if (data.status === 'classified' || data.status === 'failed') {
        return false;
      }
      return POLL_INTERVAL_MS;
    },
    refetchIntervalInBackground: false,
  });

  // Capture classification + elapsed time the first time the poll resolves
  // to a terminal state.
  useEffect(() => {
    const data = statusQuery.data;
    if (!data || classifyMs !== null) return;
    if (data.status === 'classified' || data.status === 'failed') {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: react to query terminal state once
      setClassifications(data.classifications ?? []);
      // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: latch classify_ms exactly once when polling settles
      setClassifyMs(
        submitStartedAt !== null
          ? Math.round(performance.now() - submitStartedAt)
          : null,
      );
    }
  }, [statusQuery.data, classifyMs, submitStartedAt]);

  // Hard timeout — give up polling after POLL_TIMEOUT_MS so the UI can
  // surface a "couldn't auto-tag" hint without hanging the screen.
  useEffect(() => {
    if (checkinId === null || classifyMs !== null || submitStartedAt === null) {
      return;
    }
    const remaining = POLL_TIMEOUT_MS - (performance.now() - submitStartedAt);
    if (remaining <= 0) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: hard timeout fallback so the chip never hangs
      setClassifyMs(POLL_TIMEOUT_MS);
      return;
    }
    const t = window.setTimeout(() => {
      if (classifyMs === null) {
        setClassifyMs(POLL_TIMEOUT_MS);
      }
    }, remaining);
    return () => window.clearTimeout(t);
  }, [checkinId, classifyMs, submitStartedAt]);

  const applyCorrection = async (payload: DciCorrectionPayload) => {
    if (checkinId === null) {
      throw new Error('No check-in to correct yet');
    }
    const updated = await dciApi.correct(checkinId, payload);
    setClassifications((prev) => {
      const idx = prev.findIndex((c) => c.artifact_type === payload.artifact_type);
      if (idx === -1) return [...prev, updated];
      const next = prev.slice();
      next[idx] = updated;
      return next;
    });
    return updated;
  };

  const reset = () => {
    setCheckinId(null);
    setSubmitStartedAt(null);
    setClassifyMs(null);
    setClassifications([]);
    submitMutation.reset();
  };

  return {
    submit: submitMutation.mutate,
    isSubmitting: submitMutation.isPending,
    submitError: submitMutation.error,
    checkinId,
    classifications,
    status: statusQuery.data?.status ?? (submitMutation.data ? 'pending' : null),
    classifyMs,
    applyCorrection,
    reset,
  };
}
