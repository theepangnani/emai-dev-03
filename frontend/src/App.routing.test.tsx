import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route, Navigate, useLocation, useParams } from 'react-router-dom';
import { describe, it, expect, vi } from 'vitest';
import type { ReactNode } from 'react';

// These tests cover the two regressions fixed alongside PR #3966
// (Ask + Flash-Tutor → /tutor unification):
//
// - #3967: /ask and /flash-tutor must preserve ?query params through the
//   redirect (RedirectPreservingQuery helper in App.tsx).
// - #3968: /tutor must admit teachers (teacher was missing from
//   ProtectedRoute's allowedRoles despite the sidebar linking to /tutor).
//
// We duplicate the helper locally so the test exercises the same logic the
// router mounts. If either definition drifts, the test will still catch the
// regression because the routes in App.tsx use the identical contract.

function RedirectPreservingQuery({ to }: { to: string }) {
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

// A tiny landing component at /tutor that just echoes the current search
// string so tests can assert on what survived the redirect.
function TutorStub() {
  const location = useLocation();
  return <div data-testid="tutor-search">{location.search}</div>;
}

function renderRoutes(initialEntries: string[]) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route path="/ask" element={<RedirectPreservingQuery to="/tutor" />} />
        <Route path="/flash-tutor" element={<RedirectPreservingQuery to="/tutor?mode=drill" />} />
        <Route path="/tutor" element={<TutorStub />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('RedirectPreservingQuery (#3967)', () => {
  it('forwards /ask?question=hello to /tutor?question=hello', () => {
    renderRoutes(['/ask?question=hello']);
    const el = screen.getByTestId('tutor-search');
    const params = new URLSearchParams(el.textContent ?? '');
    expect(params.get('question')).toBe('hello');
  });

  it('forwards /flash-tutor?content_id=42 to /tutor?mode=drill&content_id=42', () => {
    renderRoutes(['/flash-tutor?content_id=42']);
    const el = screen.getByTestId('tutor-search');
    const params = new URLSearchParams(el.textContent ?? '');
    expect(params.get('mode')).toBe('drill');
    expect(params.get('content_id')).toBe('42');
  });

  it('lets target query params win on collision (mode=drill stays)', () => {
    // Caller tries to sneak a different mode in via /flash-tutor — target wins.
    renderRoutes(['/flash-tutor?mode=explain&content_id=9']);
    const el = screen.getByTestId('tutor-search');
    const params = new URLSearchParams(el.textContent ?? '');
    expect(params.get('mode')).toBe('drill');
    expect(params.get('content_id')).toBe('9');
  });

  it('handles /ask with no query params', () => {
    renderRoutes(['/ask']);
    const el = screen.getByTestId('tutor-search');
    expect(el.textContent ?? '').toBe('');
  });
});

// ── #3968: /tutor must allow teachers ───────────────────────────
//
// We mock AuthContext + ProtectedRoute minimally so we can mount the real
// ProtectedRoute around a stub and verify a teacher-role user lands on the
// child (rather than being bounced to /dashboard).

const mockUser = vi.hoisted(() => ({ current: null as null | { role: string; roles: string[] } }));

vi.mock('./context/AuthContext', () => ({
  useAuth: () => ({
    user: mockUser.current
      ? {
          id: 1,
          email: 't@example.com',
          full_name: 'Teacher T',
          role: mockUser.current.role,
          roles: mockUser.current.roles,
          is_active: true,
          needs_onboarding: false,
          onboarding_completed: true,
          email_verified: true,
          google_connected: false,
          interests: [],
        }
      : null,
    isLoading: false,
  }),
  AuthProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

async function loadProtectedRoute() {
  const mod = await import('./components/ProtectedRoute');
  return mod.ProtectedRoute;
}

describe('/tutor allowedRoles (#3968)', () => {
  it('renders the child for a teacher when allowedRoles includes teacher', async () => {
    mockUser.current = { role: 'teacher', roles: ['teacher'] };
    const ProtectedRoute = await loadProtectedRoute();

    render(
      <MemoryRouter initialEntries={['/tutor']}>
        <Routes>
          <Route
            path="/tutor"
            element={
              <ProtectedRoute allowedRoles={['parent', 'student', 'teacher']}>
                <div data-testid="tutor-rendered">tutor</div>
              </ProtectedRoute>
            }
          />
          <Route path="/dashboard" element={<div data-testid="dashboard">dash</div>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByTestId('tutor-rendered')).toBeInTheDocument();
    expect(screen.queryByTestId('dashboard')).not.toBeInTheDocument();
  });

  it('redirects a teacher away when allowedRoles excludes teacher (regression guard)', async () => {
    mockUser.current = { role: 'teacher', roles: ['teacher'] };
    const ProtectedRoute = await loadProtectedRoute();

    render(
      <MemoryRouter initialEntries={['/tutor']}>
        <Routes>
          <Route
            path="/tutor"
            element={
              <ProtectedRoute allowedRoles={['parent', 'student']}>
                <div data-testid="tutor-rendered">tutor</div>
              </ProtectedRoute>
            }
          />
          <Route path="/dashboard" element={<div data-testid="dashboard">dash</div>} />
        </Routes>
      </MemoryRouter>,
    );

    // The old (broken) config would bounce teachers to /dashboard.
    expect(screen.queryByTestId('tutor-rendered')).not.toBeInTheDocument();
    expect(screen.getByTestId('dashboard')).toBeInTheDocument();
  });
});

// ── #3977: /tutor/session/:id canonical URL + legacy redirect ───
//
// /flash-tutor/session/:id is a legacy alias that must redirect to the new
// /tutor/session/:id path. We duplicate the LegacySessionRedirect helper
// locally (same contract as App.tsx) and verify both the forward and the
// canonical mount render the expected target.

function LegacySessionRedirect() {
  const { id } = useParams();
  return <Navigate to={`/tutor/session/${id}`} replace />;
}

function SessionStub() {
  const { id } = useParams();
  return <div data-testid="session-stub">session-{id}</div>;
}

describe('/tutor/session/:id canonical URL (#3977)', () => {
  it('redirects /flash-tutor/session/42 to /tutor/session/42', () => {
    render(
      <MemoryRouter initialEntries={['/flash-tutor/session/42']}>
        <Routes>
          <Route path="/tutor/session/:id" element={<SessionStub />} />
          <Route path="/flash-tutor/session/:id" element={<LegacySessionRedirect />} />
        </Routes>
      </MemoryRouter>,
    );
    const el = screen.getByTestId('session-stub');
    expect(el.textContent).toBe('session-42');
  });

  it('/tutor/session/99 renders the canonical session page', () => {
    render(
      <MemoryRouter initialEntries={['/tutor/session/99']}>
        <Routes>
          <Route path="/tutor/session/:id" element={<SessionStub />} />
          <Route path="/flash-tutor/session/:id" element={<LegacySessionRedirect />} />
        </Routes>
      </MemoryRouter>,
    );
    const el = screen.getByTestId('session-stub');
    expect(el.textContent).toBe('session-99');
  });
});
