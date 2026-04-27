/** CB-KIDPHOTO-001 (#4301) — light coverage for the avatar upload flow. */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../../test/helpers';
import { KidHero } from './KidHero';
import type { ChildSummary } from '../../api/client';

const mockUploadKidPhoto = vi.fn();

vi.mock('../../api/kidPhoto', () => ({
  uploadKidPhoto: (...args: unknown[]) => mockUploadKidPhoto(...args),
  deleteKidPhoto: vi.fn(),
}));

vi.mock('../OnTrackBadge', () => ({
  OnTrackBadge: () => <div data-testid="ontrack-badge" />,
}));

vi.mock('../Toast', () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

const baseChild: ChildSummary = {
  student_id: 1,
  user_id: 11,
  full_name: 'Aanya Kumar',
  email: 'aanya@test.com',
  grade_level: 8,
  school_name: 'Bridge School',
  date_of_birth: null,
  phone: null,
  address: null,
  city: null,
  province: null,
  postal_code: null,
  notes: null,
  interests: [],
  relationship_type: 'guardian',
  invite_link: null,
  course_count: 4,
  active_task_count: 2,
  invite_status: 'active',
  invite_id: null,
  profile_photo_url: null,
};

const noopProps = {
  color: '#b84c2f',
  onOpenTutor: vi.fn(),
  onEdit: vi.fn(),
  onExport: vi.fn(),
  onRemove: vi.fn(),
};

beforeEach(() => {
  mockUploadKidPhoto.mockReset();
});

describe('KidHero — profile photo upload', () => {
  it('renders the initial when no profile_photo_url is set', () => {
    renderWithProviders(<KidHero child={baseChild} {...noopProps} />);
    expect(screen.getByText('A')).toBeInTheDocument();
  });

  it('renders the photo when profile_photo_url is set', () => {
    renderWithProviders(
      <KidHero
        child={{ ...baseChild, profile_photo_url: 'https://example.com/photo.jpg' }}
        {...noopProps}
      />,
    );
    const img = screen.getByRole('button', { name: /change profile photo/i }).querySelector('img');
    expect(img).not.toBeNull();
    expect(img?.getAttribute('src')).toBe('https://example.com/photo.jpg');
  });

  it('uploads the file and calls onPhotoChange on success', async () => {
    mockUploadKidPhoto.mockResolvedValue({ profile_photo_url: 'https://example.com/new.jpg' });
    const onPhotoChange = vi.fn();
    const user = userEvent.setup();

    renderWithProviders(
      <KidHero child={baseChild} {...noopProps} onPhotoChange={onPhotoChange} />,
    );

    const file = new File(['fake-bytes'], 'avatar.jpg', { type: 'image/jpeg' });
    // The hidden <input type="file"> is the actual upload mechanism.
    const input = document.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    expect(input).not.toBeNull();
    await user.upload(input, file);

    await waitFor(() => {
      expect(mockUploadKidPhoto).toHaveBeenCalledWith(baseChild.student_id, file);
    });
    await waitFor(() => {
      expect(onPhotoChange).toHaveBeenCalledWith('https://example.com/new.jpg');
    });
  });
});
