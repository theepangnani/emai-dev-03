import { Navigate, useLocation, useParams } from 'react-router-dom';

/** Redirect that merges source search params into the target (target wins on collision). */
export function RedirectPreservingQuery({ to }: { to: string }) {
  const location = useLocation();
  const [pathname, targetSearch] = to.split('?');
  const source = new URLSearchParams(location.search);
  const target = new URLSearchParams(targetSearch ?? '');
  source.forEach((v, k) => {
    if (!target.has(k)) target.set(k, v);
  });
  const qs = target.toString();
  return <Navigate to={qs ? `${pathname}?${qs}` : pathname} replace />;
}

/** Redirects legacy /flash-tutor/session/:id → /tutor/session/:id. */
export function LegacySessionRedirect() {
  const { id } = useParams();
  return <Navigate to={`/tutor/session/${id}`} replace />;
}
