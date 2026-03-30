import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../../test/helpers';
import type { ResourceLinkGroup } from '../../api/resourceLinks';

const mockList = vi.fn();
const mockDelete = vi.fn();
const mockPin = vi.fn();
const mockDismiss = vi.fn();

vi.mock('../../api/resourceLinks', () => ({
  resourceLinksApi: {
    list: (...args: unknown[]) => mockList(...args),
    add: vi.fn(),
    delete: (...args: unknown[]) => mockDelete(...args),
    pin: (...args: unknown[]) => mockPin(...args),
    dismiss: (...args: unknown[]) => mockDismiss(...args),
    reExtract: vi.fn(),
  },
}));

import { VideosLinksTab } from './VideosLinksTab';

const teacherLink = {
  id: 1,
  course_content_id: 10,
  url: 'https://example.com/notes',
  resource_type: 'link',
  title: 'Teacher Notes',
  topic_heading: 'Unit 1',
  description: null,
  thumbnail_url: null,
  youtube_video_id: null,
  display_order: 0,
  created_at: '2026-01-01',
  source: 'teacher_shared',
};

const aiLink = {
  id: 2,
  course_content_id: 10,
  url: 'https://example.com/ai-resource',
  resource_type: 'link',
  title: 'AI Resource',
  topic_heading: 'Unit 1',
  description: null,
  thumbnail_url: null,
  youtube_video_id: null,
  display_order: 1,
  created_at: '2026-01-02',
  source: 'ai_suggested',
};

const aiYouTubeLink = {
  id: 3,
  course_content_id: 10,
  url: 'https://youtube.com/watch?v=abc123',
  resource_type: 'youtube',
  title: 'AI Video',
  topic_heading: 'Unit 1',
  description: 'A helpful video',
  thumbnail_url: null,
  youtube_video_id: 'abc123',
  display_order: 2,
  created_at: '2026-01-03',
  source: 'ai_suggested',
};

function makeGroups(links: typeof teacherLink[]): ResourceLinkGroup[] {
  const map = new Map<string | null, typeof teacherLink[]>();
  for (const l of links) {
    const arr = map.get(l.topic_heading) || [];
    arr.push(l);
    map.set(l.topic_heading, arr);
  }
  return Array.from(map.entries()).map(([heading, items]) => ({
    topic_heading: heading,
    links: items,
  }));
}

describe('VideosLinksTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders teacher links without AI section when no AI links', async () => {
    mockList.mockResolvedValue(makeGroups([teacherLink]));
    renderWithProviders(<VideosLinksTab courseContentId={10} />);

    await waitFor(() => {
      expect(screen.getByText('Teacher Notes')).toBeInTheDocument();
    });
    expect(screen.queryByText('AI-Suggested Resources')).not.toBeInTheDocument();
  });

  it('renders AI-Suggested Resources section with badge', async () => {
    mockList.mockResolvedValue(makeGroups([teacherLink, aiLink]));
    renderWithProviders(<VideosLinksTab courseContentId={10} />);

    await waitFor(() => {
      expect(screen.getByText('AI-Suggested Resources')).toBeInTheDocument();
    });
    expect(screen.getByText('AI Resource')).toBeInTheDocument();
    expect(screen.getAllByText('AI-suggested').length).toBeGreaterThan(0);
  });

  it('calls pin API when pin button is clicked', async () => {
    mockList.mockResolvedValue(makeGroups([aiLink]));
    mockPin.mockResolvedValue({ ...aiLink, source: 'teacher_shared' });
    const user = userEvent.setup();

    renderWithProviders(<VideosLinksTab courseContentId={10} />);

    await waitFor(() => {
      expect(screen.getByText('AI Resource')).toBeInTheDocument();
    });

    const pinBtn = screen.getByTitle('Pin as permanent resource');
    await user.click(pinBtn);

    expect(mockPin).toHaveBeenCalledWith(2);
  });

  it('calls dismiss API when dismiss button is clicked', async () => {
    mockList.mockResolvedValue(makeGroups([aiLink]));
    mockDismiss.mockResolvedValue(undefined);
    const user = userEvent.setup();

    renderWithProviders(<VideosLinksTab courseContentId={10} />);

    await waitFor(() => {
      expect(screen.getByText('AI Resource')).toBeInTheDocument();
    });

    const dismissBtn = screen.getByTitle('Dismiss suggestion');
    await user.click(dismissBtn);

    expect(mockDismiss).toHaveBeenCalledWith(2);
  });

  it('does not show AI section when all links are teacher_shared', async () => {
    mockList.mockResolvedValue(makeGroups([teacherLink]));
    renderWithProviders(<VideosLinksTab courseContentId={10} />);

    await waitFor(() => {
      expect(screen.getByText('Teacher Notes')).toBeInTheDocument();
    });
    expect(screen.queryByText('AI-Suggested Resources')).not.toBeInTheDocument();
    expect(screen.queryByText('AI-suggested')).not.toBeInTheDocument();
  });

  it('renders AI-suggested YouTube videos with badge', async () => {
    mockList.mockResolvedValue(makeGroups([aiYouTubeLink]));
    renderWithProviders(<VideosLinksTab courseContentId={10} />);

    await waitFor(() => {
      expect(screen.getByText('AI-Suggested Resources')).toBeInTheDocument();
    });
    expect(screen.getByText('AI Video')).toBeInTheDocument();
    expect(screen.getAllByText('AI-suggested').length).toBeGreaterThan(0);
  });
});
