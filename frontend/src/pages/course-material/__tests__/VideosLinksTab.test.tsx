import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { VideosLinksTab } from '../VideosLinksTab';
import type { ResourceLinkGroup } from '../../../api/resourceLinks';

// Mock the resourceLinks API module
vi.mock('../../../api/resourceLinks', () => ({
  resourceLinksApi: {
    list: vi.fn(),
    add: vi.fn(),
    delete: vi.fn(),
    reExtract: vi.fn(),
  },
}));

import { resourceLinksApi } from '../../../api/resourceLinks';

const mockedApi = vi.mocked(resourceLinksApi);

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

const YOUTUBE_GROUPS: ResourceLinkGroup[] = [
  {
    topic_heading: 'Analytic Geometry',
    links: [
      {
        id: 1,
        course_content_id: 100,
        url: 'https://www.youtube.com/watch?v=ABC123',
        resource_type: 'youtube',
        title: 'Equation of the median',
        topic_heading: 'Analytic Geometry',
        description: 'A great video about medians',
        thumbnail_url: null,
        youtube_video_id: 'ABC123',
        display_order: 0,
        created_at: '2026-03-01T00:00:00Z',
      },
    ],
  },
];

const MIXED_GROUPS: ResourceLinkGroup[] = [
  {
    topic_heading: 'Analytic Geometry',
    links: [
      {
        id: 1,
        course_content_id: 100,
        url: 'https://www.youtube.com/watch?v=ABC123',
        resource_type: 'youtube',
        title: 'Equation of the median',
        topic_heading: 'Analytic Geometry',
        description: null,
        thumbnail_url: null,
        youtube_video_id: 'ABC123',
        display_order: 0,
        created_at: '2026-03-01T00:00:00Z',
      },
    ],
  },
  {
    topic_heading: 'Resources',
    links: [
      {
        id: 2,
        course_content_id: 100,
        url: 'https://example.com/docs',
        resource_type: 'external_link',
        title: 'Example Docs',
        topic_heading: 'Resources',
        description: null,
        thumbnail_url: null,
        youtube_video_id: null,
        display_order: 0,
        created_at: '2026-03-01T00:00:00Z',
      },
    ],
  },
];

beforeEach(() => {
  vi.clearAllMocks();
});

describe('VideosLinksTab', () => {
  it('renders empty state when no links', async () => {
    mockedApi.list.mockResolvedValue([]);

    render(<VideosLinksTab courseContentId={100} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('No videos or links found')).toBeInTheDocument();
    });
  });

  it('renders YouTube embeds with correct src', async () => {
    mockedApi.list.mockResolvedValue(YOUTUBE_GROUPS);

    render(<VideosLinksTab courseContentId={100} />, { wrapper: createWrapper() });

    await waitFor(() => {
      const iframe = document.querySelector('iframe');
      expect(iframe).not.toBeNull();
      expect(iframe!.getAttribute('src')).toBe('https://www.youtube.com/embed/ABC123');
    });
  });

  it('renders topic group headings', async () => {
    mockedApi.list.mockResolvedValue(MIXED_GROUPS);

    render(<VideosLinksTab courseContentId={100} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Analytic Geometry')).toBeInTheDocument();
      expect(screen.getByText('Resources')).toBeInTheDocument();
    });
  });

  it('renders link cards for non-YouTube links', async () => {
    mockedApi.list.mockResolvedValue(MIXED_GROUPS);

    render(<VideosLinksTab courseContentId={100} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Example Docs')).toBeInTheDocument();
    });

    // The external link should be an anchor tag
    const link = screen.getByText('Example Docs').closest('a');
    expect(link).not.toBeNull();
    expect(link!.getAttribute('href')).toBe('https://example.com/docs');
    expect(link!.getAttribute('target')).toBe('_blank');
  });

  it('toggles add link form on button click', async () => {
    mockedApi.list.mockResolvedValue(MIXED_GROUPS);
    const user = userEvent.setup();

    render(<VideosLinksTab courseContentId={100} />, { wrapper: createWrapper() });

    // Wait for content to load
    await waitFor(() => {
      expect(screen.getByText('Analytic Geometry')).toBeInTheDocument();
    });

    // Click "Add Link" button
    const addBtn = screen.getByRole('button', { name: /add link/i });
    await user.click(addBtn);

    // Form should appear with URL input
    expect(screen.getByPlaceholderText('https://...')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Title (optional)')).toBeInTheDocument();
  });

  it('collapses and expands topic groups', async () => {
    mockedApi.list.mockResolvedValue(YOUTUBE_GROUPS);
    const user = userEvent.setup();

    render(<VideosLinksTab courseContentId={100} />, { wrapper: createWrapper() });

    // Wait for content
    await waitFor(() => {
      expect(screen.getByText('Analytic Geometry')).toBeInTheDocument();
    });

    // iframe should be visible initially
    expect(document.querySelector('iframe')).not.toBeNull();

    // Click the heading to collapse
    await user.click(screen.getByText('Analytic Geometry'));

    // iframe should be hidden after collapse
    expect(document.querySelector('iframe')).toBeNull();

    // Click again to expand
    await user.click(screen.getByText('Analytic Geometry'));

    // iframe should reappear
    await waitFor(() => {
      expect(document.querySelector('iframe')).not.toBeNull();
    });
  });

  it('shows link count in toolbar', async () => {
    mockedApi.list.mockResolvedValue(MIXED_GROUPS);

    render(<VideosLinksTab courseContentId={100} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('2 links')).toBeInTheDocument();
    });
  });
});
