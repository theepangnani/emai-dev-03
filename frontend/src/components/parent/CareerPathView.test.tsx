import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CareerPathView } from './CareerPathView';
import type { CareerPathAnalysis } from '../../api/schoolReportCards';

const mockCareerPath: CareerPathAnalysis = {
  id: 1,
  student_id: 10,
  strengths: ['Mathematics', 'Problem Solving', 'Critical Thinking'],
  grade_trends: [
    { subject: 'Math', trajectory: 'improving', data: '75 -> 85', note: 'Consistent improvement' },
    { subject: 'Science', trajectory: 'stable', data: '80 -> 80', note: 'Maintaining strong performance' },
    { subject: 'English', trajectory: 'declining', data: '90 -> 78', note: 'Needs attention' },
  ],
  career_suggestions: [
    {
      career: 'Software Engineer',
      reasoning: 'Strong math and problem-solving skills',
      related_subjects: ['Math', 'Science'],
      next_steps: 'Consider coding courses',
    },
    {
      career: 'Data Scientist',
      reasoning: 'Analytical thinking and math aptitude',
      related_subjects: ['Math', 'Statistics'],
      next_steps: 'Explore data analysis projects',
    },
  ],
  overall_assessment: 'Alice shows strong analytical abilities with room for growth in language arts.',
  report_cards_analyzed: 3,
  created_at: '2026-03-20T10:00:00Z',
};

describe('CareerPathView', () => {
  it('renders strengths badges', () => {
    render(<CareerPathView careerPath={mockCareerPath} />);
    expect(screen.getByText('Mathematics')).toBeInTheDocument();
    expect(screen.getByText('Problem Solving')).toBeInTheDocument();
    expect(screen.getByText('Critical Thinking')).toBeInTheDocument();
  });

  it('renders grade trends with trajectories', () => {
    render(<CareerPathView careerPath={mockCareerPath} />);
    expect(screen.getByText('Consistent improvement')).toBeInTheDocument();
    expect(screen.getByText('Maintaining strong performance')).toBeInTheDocument();
    expect(screen.getByText('Needs attention')).toBeInTheDocument();
    expect(screen.getByText('75 -> 85')).toBeInTheDocument();
    expect(screen.getByText('80 -> 80')).toBeInTheDocument();
    expect(screen.getByText('90 -> 78')).toBeInTheDocument();
  });

  it('renders career suggestion cards', () => {
    render(<CareerPathView careerPath={mockCareerPath} />);
    expect(screen.getByText('Software Engineer')).toBeInTheDocument();
    expect(screen.getByText('Data Scientist')).toBeInTheDocument();
    expect(screen.getByText('Strong math and problem-solving skills')).toBeInTheDocument();
    expect(screen.getByText('Consider coding courses')).toBeInTheDocument();
    expect(screen.getByText('Explore data analysis projects')).toBeInTheDocument();
  });

  it('renders overall assessment', () => {
    render(<CareerPathView careerPath={mockCareerPath} />);
    expect(screen.getByText('Alice shows strong analytical abilities with room for growth in language arts.')).toBeInTheDocument();
  });

  it('renders report cards analyzed count', () => {
    render(<CareerPathView careerPath={mockCareerPath} />);
    expect(screen.getByText(/3 report cards/)).toBeInTheDocument();
  });

  it('renders section headings', () => {
    render(<CareerPathView careerPath={mockCareerPath} />);
    expect(screen.getByText('Academic Strengths')).toBeInTheDocument();
    expect(screen.getByText('Grade Trends')).toBeInTheDocument();
    expect(screen.getByText('Career Suggestions')).toBeInTheDocument();
    expect(screen.getByText('Overall Assessment')).toBeInTheDocument();
  });
});
