import { render, screen, waitFor } from '@testing-library/react';

const mockGetWaitlistStats = vi.fn();

vi.mock('../../api/public', () => ({
  getWaitlistStats: () => mockGetWaitlistStats(),
}));

import { ProofWall } from './ProofWall';

// ── test fixtures ───────────────────────────────────────────────

const defaultTestimonials = {
  testimonials: [
    { id: 't1', quote: 'pending', role: 'parent', city: 'Markham', status: 'pending_consent' },
    { id: 't2', quote: 'pending', role: 'teacher', city: 'Toronto', status: 'pending_consent' },
  ],
};

const defaultBadges = {
  badges: [
    { id: 'canada-hosted', label: 'Hosted in Canada (GCP Toronto)', href: '/compliance#hosting' },
    { id: 'mfippa', label: 'MFIPPA-aligned', href: '/compliance#mfippa' },
    { id: 'pipeda', label: 'PIPEDA-compliant', href: '/compliance#pipeda' },
    { id: 'canadian-stack', label: 'Canadian-hosted stack', href: '/compliance#stack' },
  ],
};

function mockFetch(
  overrides: { testimonials?: unknown; badges?: unknown } = {},
) {
  const testimonials = overrides.testimonials ?? defaultTestimonials;
  const badges = overrides.badges ?? defaultBadges;

  global.fetch = vi.fn((url: RequestInfo | URL) => {
    const u = String(url);
    if (u.includes('testimonials.json')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(testimonials),
      } as Response);
    }
    if (u.includes('compliance-badges.json')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(badges),
      } as Response);
    }
    return Promise.reject(new Error(`Unexpected fetch: ${u}`));
  }) as unknown as typeof fetch;
}

function mockMatchMedia(reduced: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn((query: string) => ({
      matches: query.includes('prefers-reduced-motion') ? reduced : false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    })),
  });
}

describe('ProofWall', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch();
    mockMatchMedia(true); // Default: reduced-motion so count-up resolves instantly.
    mockGetWaitlistStats.mockResolvedValue({ total: null, by_municipality: [] });
  });

  it('hides counter when total is null; still renders badges', async () => {
    mockGetWaitlistStats.mockResolvedValue({ total: null, by_municipality: [] });

    render(<ProofWall />);

    await waitFor(() => {
      expect(screen.getByTestId('proof-wall-badges')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('proof-wall-counter')).not.toBeInTheDocument();
  });

  it('still renders testimonials when total is null and testimonials are consented', async () => {
    mockGetWaitlistStats.mockResolvedValue({ total: null, by_municipality: [] });
    mockFetch({
      testimonials: {
        testimonials: [
          { id: 't1', quote: 'Love this app', role: 'parent', city: 'Markham' },
        ],
      },
    });

    render(<ProofWall />);

    await waitFor(() => {
      expect(screen.getByText('Love this app')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('proof-wall-counter')).not.toBeInTheDocument();
  });

  it('renders counter with total when total is 120', async () => {
    mockGetWaitlistStats.mockResolvedValue({ total: 120, by_municipality: [] });

    render(<ProofWall />);

    await waitFor(() => {
      expect(screen.getByTestId('proof-wall-counter')).toBeInTheDocument();
    });
    expect(screen.getByText('120')).toBeInTheDocument();
    expect(screen.getByText(/Ontario families on the waitlist/i)).toBeInTheDocument();
  });

  it('runs count-up animation via requestAnimationFrame when motion is allowed', async () => {
    mockMatchMedia(false);
    const rafSpy = vi.spyOn(window, 'requestAnimationFrame');
    mockGetWaitlistStats.mockResolvedValue({ total: 120, by_municipality: [] });

    render(<ProofWall />);

    await waitFor(() => {
      expect(screen.getByTestId('proof-wall-counter')).toBeInTheDocument();
    });
    expect(rafSpy).toHaveBeenCalled();
    rafSpy.mockRestore();
  });

  it('renders top municipality line when top count >= 3', async () => {
    mockGetWaitlistStats.mockResolvedValue({
      total: 120,
      by_municipality: [{ name: 'Markham', count: 37 }],
    });

    render(<ProofWall />);

    await waitFor(() => {
      expect(screen.getByText('37 from Markham')).toBeInTheDocument();
    });
  });

  it('hides municipality line when top count < 3', async () => {
    mockGetWaitlistStats.mockResolvedValue({
      total: 120,
      by_municipality: [{ name: 'Toronto', count: 2 }],
    });

    render(<ProofWall />);

    await waitFor(() => {
      expect(screen.getByTestId('proof-wall-counter')).toBeInTheDocument();
    });
    expect(screen.queryByText(/from Toronto/i)).not.toBeInTheDocument();
  });

  it('renders no testimonials section when all are pending_consent', async () => {
    mockFetch({ testimonials: defaultTestimonials }); // All pending.

    render(<ProofWall />);

    // Wait for badges so we know fetches have resolved.
    await waitFor(() => {
      expect(screen.getByTestId('proof-wall-badges')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('proof-wall-testimonials')).not.toBeInTheDocument();
  });

  it('renders only consented testimonials', async () => {
    mockFetch({
      testimonials: {
        testimonials: [
          { id: 't1', quote: 'Pending quote', role: 'parent', city: 'Markham', status: 'pending_consent' },
          { id: 't2', quote: 'Consented quote here', role: 'teacher', city: 'Toronto' },
        ],
      },
    });

    render(<ProofWall />);

    await waitFor(() => {
      expect(screen.getByText('Consented quote here')).toBeInTheDocument();
    });
    expect(screen.queryByText('Pending quote')).not.toBeInTheDocument();
    expect(screen.getByText(/teacher, Toronto/)).toBeInTheDocument();
  });

  it('renders compliance badges as anchor elements with correct hrefs', async () => {
    render(<ProofWall />);

    await waitFor(() => {
      expect(screen.getByTestId('proof-wall-badges')).toBeInTheDocument();
    });

    const hosting = screen.getByRole('listitem', { name: /Hosted in Canada/i });
    expect(hosting.tagName).toBe('A');
    expect(hosting).toHaveAttribute('href', '/compliance#hosting');

    expect(screen.getByRole('listitem', { name: /MFIPPA-aligned/i })).toHaveAttribute(
      'href',
      '/compliance#mfippa',
    );
    expect(screen.getByRole('listitem', { name: /PIPEDA-compliant/i })).toHaveAttribute(
      'href',
      '/compliance#pipeda',
    );
    expect(
      screen.getByRole('listitem', { name: /Canadian-hosted stack/i }),
    ).toHaveAttribute('href', '/compliance#stack');
  });

  it('skips count-up animation when prefers-reduced-motion is set', async () => {
    mockMatchMedia(true);
    const rafSpy = vi.spyOn(window, 'requestAnimationFrame');
    mockGetWaitlistStats.mockResolvedValue({ total: 120, by_municipality: [] });

    render(<ProofWall />);

    // Total should appear instantly (no animation frames scheduled).
    await waitFor(() => {
      expect(screen.getByText('120')).toBeInTheDocument();
    });
    expect(rafSpy).not.toHaveBeenCalled();
    rafSpy.mockRestore();
  });

  it('degrades gracefully when waitlist-stats fetch fails (no counter; testimonials + badges still render)', async () => {
    mockGetWaitlistStats.mockRejectedValue(new Error('network'));
    mockFetch({
      testimonials: {
        testimonials: [
          { id: 't1', quote: 'Still here', role: 'parent', city: 'Markham' },
        ],
      },
    });

    render(<ProofWall />);

    await waitFor(() => {
      expect(screen.getByText('Still here')).toBeInTheDocument();
    });
    expect(screen.getByTestId('proof-wall-badges')).toBeInTheDocument();
    expect(screen.queryByTestId('proof-wall-counter')).not.toBeInTheDocument();
  });
});
