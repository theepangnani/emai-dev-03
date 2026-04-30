/**
 * CB-CMCP-001 M3β follow-up #4694 — Student artifact view page.
 *
 * Minimal landing page for LTI-launched STUDENT users. The 3E-4 LTI
 * launch endpoint (`GET /api/lti/launch`) validates the JWT, resolves
 * the kid_id to a STUDENT user, and 302-redirects here:
 *
 *   /student/artifact/:artifact_id
 *
 * This is intentionally minimal for M3β — fetch the artifact via
 * `/api/cmcp/artifacts/{id}/student-view` and render the title +
 * content. M4 will polish UX (drill anchors, persona-correct shells,
 * Arc voice integration). For today, "the launching student lands on
 * something that loads and renders" is the correctness bar — gating
 * the redirect to a parent-only route was the original CRITICAL bug.
 *
 * Route gating: ProtectedRoute allowedRoles={['student']} in App.tsx.
 */
import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { DashboardLayout } from '../../components/DashboardLayout';
import {
  cmcpStudentArtifactApi,
  type StudentArtifactView,
} from '../../api/cmcpStudentArtifact';

type LoadState = 'loading' | 'ready' | 'error';

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

function LoadingState() {
  return (
    <div role="status" aria-live="polite" data-testid="student-artifact-loading">
      <h2>Loading artifact…</h2>
    </div>
  );
}

function ErrorState({ error }: { error: ErrorShape }) {
  let title = 'Something went wrong';
  let body = error.message;
  if (error.status === 404) {
    title = 'Artifact not found';
    body =
      "We couldn't find this artifact. It may have been removed, or it isn't visible to you.";
  } else if (error.status === 403) {
    title = "You don't have access";
    body = "This artifact isn't available to your account.";
  } else if (error.status === 401) {
    title = 'Please sign in again';
    body = 'Your session has expired. Sign in to view the artifact.';
  }
  return (
    <div role="alert" data-testid="student-artifact-error">
      <h2>{title}</h2>
      <p>{body}</p>
    </div>
  );
}

interface ArtifactBodyProps {
  artifact: StudentArtifactView;
}

function ArtifactBody({ artifact }: ArtifactBodyProps) {
  return (
    <article data-testid="student-artifact-body">
      <header>
        <h1>{artifact.title}</h1>
      </header>
      <section data-testid="student-artifact-content">
        <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>
          {artifact.content}
        </pre>
      </section>
    </article>
  );
}

export function StudentArtifactPage() {
  const { artifact_id: artifactId } = useParams<{ artifact_id: string }>();
  const missingId = !artifactId;

  const [state, setState] = useState<LoadState>(
    missingId ? 'error' : 'loading',
  );
  const [artifact, setArtifact] = useState<StudentArtifactView | null>(null);
  const [error, setError] = useState<ErrorShape | null>(
    missingId ? { message: 'Missing artifact id in URL.' } : null,
  );

  // Reset-on-id-change pattern (mirrors ParentCompanionPage) — derive
  // a "previous artifactId" from state and reset during render when
  // the URL param changes.
  const [prevArtifactId, setPrevArtifactId] = useState(artifactId);
  if (prevArtifactId !== artifactId) {
    setPrevArtifactId(artifactId);
    setState(missingId ? 'error' : 'loading');
    setArtifact(null);
    setError(missingId ? { message: 'Missing artifact id in URL.' } : null);
  }

  useEffect(() => {
    if (!artifactId) {
      return;
    }
    let cancelled = false;

    cmcpStudentArtifactApi
      .get(artifactId)
      .then((data) => {
        if (cancelled) return;
        setArtifact(data);
        setState('ready');
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
    <DashboardLayout welcomeSubtitle="Artifact">
      <div data-testid="student-artifact-page">
        {state === 'loading' && <LoadingState />}
        {state === 'error' && error && <ErrorState error={error} />}
        {state === 'ready' && artifact && <ArtifactBody artifact={artifact} />}
      </div>
    </DashboardLayout>
  );
}

export default StudentArtifactPage;
