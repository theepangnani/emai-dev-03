import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StudyRequestModal } from '../StudyRequestModal';

// Mock useFocusTrap
vi.mock('../../hooks/useFocusTrap', () => ({
  useFocusTrap: () => ({ current: null }),
}));

// Mock studyRequestsApi
vi.mock('../../api/studyRequests', () => ({
  studyRequestsApi: {
    create: vi.fn().mockResolvedValue({ id: 1, subject: 'Math', status: 'pending' }),
  },
}));

const defaultChildren = [
  { student_id: 1, user_id: 10, full_name: 'Child One' },
  { student_id: 2, user_id: 20, full_name: 'Child Two' },
];

describe('StudyRequestModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders when open', () => {
    render(
      <StudyRequestModal
        open={true}
        onClose={vi.fn()}
        children={defaultChildren}
      />
    );
    expect(screen.getByText('Request Study Session')).toBeInTheDocument();
    expect(screen.getByText(/Suggest a topic/i)).toBeInTheDocument();
  });

  it('does not render when closed', () => {
    render(
      <StudyRequestModal
        open={false}
        onClose={vi.fn()}
        children={defaultChildren}
      />
    );
    expect(screen.queryByText('Request Study Session')).not.toBeInTheDocument();
  });

  it('shows child selector when multiple children', () => {
    render(
      <StudyRequestModal
        open={true}
        onClose={vi.fn()}
        children={defaultChildren}
      />
    );
    expect(screen.getByText('Child One')).toBeInTheDocument();
    expect(screen.getByText('Child Two')).toBeInTheDocument();
  });

  it('shows subject and topic inputs', () => {
    render(
      <StudyRequestModal
        open={true}
        onClose={vi.fn()}
        children={defaultChildren}
      />
    );
    expect(screen.getByPlaceholderText(/Math, Science/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Fractions, Photosynthesis/i)).toBeInTheDocument();
  });

  it('shows urgency dropdown', () => {
    render(
      <StudyRequestModal
        open={true}
        onClose={vi.fn()}
        children={defaultChildren}
      />
    );
    expect(screen.getByText(/when they have time/i)).toBeInTheDocument();
    expect(screen.getByText(/this week/i)).toBeInTheDocument();
    expect(screen.getByText(/before the next class/i)).toBeInTheDocument();
  });
});
