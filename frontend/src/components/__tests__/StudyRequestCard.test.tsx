import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { StudyRequestCard } from '../StudyRequestCard';
import type { StudyRequestData } from '../../api/studyRequests';

// Mock studyRequestsApi
vi.mock('../../api/studyRequests', () => ({
  studyRequestsApi: {
    respond: vi.fn().mockResolvedValue({}),
  },
}));

const mockRequest: StudyRequestData = {
  id: 1,
  parent_id: 10,
  student_id: 20,
  subject: 'Math',
  topic: 'Fractions',
  urgency: 'normal',
  message: 'Please review before Friday',
  status: 'pending',
  student_response: null,
  responded_at: null,
  created_at: '2026-03-20T10:00:00Z',
  parent_name: 'Mom',
};

describe('StudyRequestCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders nothing when no requests', () => {
    const { container } = render(
      <MemoryRouter>
        <StudyRequestCard requests={[]} />
      </MemoryRouter>
    );
    expect(container.innerHTML).toBe('');
  });

  it('renders request details', () => {
    render(
      <MemoryRouter>
        <StudyRequestCard requests={[mockRequest]} />
      </MemoryRouter>
    );
    expect(screen.getByText('Study Requests from Parent')).toBeInTheDocument();
    expect(screen.getByText(/Mom suggested/)).toBeInTheDocument();
    expect(screen.getByText(/Math/)).toBeInTheDocument();
    expect(screen.getByText(/Fractions/)).toBeInTheDocument();
  });

  it('renders action buttons', () => {
    render(
      <MemoryRouter>
        <StudyRequestCard requests={[mockRequest]} />
      </MemoryRouter>
    );
    expect(screen.getByText('Accept')).toBeInTheDocument();
    expect(screen.getByText('Defer')).toBeInTheDocument();
    expect(screen.getByText('Done')).toBeInTheDocument();
  });

  it('shows parent message', () => {
    render(
      <MemoryRouter>
        <StudyRequestCard requests={[mockRequest]} />
      </MemoryRouter>
    );
    expect(screen.getByText(/"Please review before Friday"/)).toBeInTheDocument();
  });
});
