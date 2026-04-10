import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ClassificationBar, getMaterialTypeLabel } from '../ClassificationBar';

describe('ClassificationBar', () => {
  const defaultProps = {
    documentType: 'teacher_notes' as string | null,
    detectedSubject: 'math' as string | null,
    confidence: 0.92,
    childName: null as string | null,
    childGrade: null as string | null,
    materialTypeDisplay: 'Teacher Notes' as string | null,
    isClassifying: false,
    onEditClick: vi.fn(),
  };

  it('renders loading state when classifying', () => {
    render(<ClassificationBar {...defaultProps} isClassifying={true} />);
    expect(screen.getByText('Analyzing your document...')).toBeInTheDocument();
  });

  it('renders high-confidence classification', () => {
    render(<ClassificationBar {...defaultProps} />);
    expect(screen.getByText(/looks like/)).toBeInTheDocument();
    expect(screen.getByText('Not right?')).toBeInTheDocument();
  });

  it('renders low-confidence classification with "might be"', () => {
    render(<ClassificationBar {...defaultProps} confidence={0.5} />);
    expect(screen.getByText(/might be/)).toBeInTheDocument();
    expect(screen.getByText('Confirm or change')).toBeInTheDocument();
  });

  it('renders unknown state when confidence is 0', () => {
    render(<ClassificationBar {...defaultProps} confidence={0} detectedSubject={null} />);
    expect(screen.getByText(/couldn't determine/i)).toBeInTheDocument();
    expect(screen.getByText('Tell us what it is')).toBeInTheDocument();
  });

  it('shows child name when provided', () => {
    render(<ClassificationBar {...defaultProps} childName="Emma" />);
    expect(screen.getByText('Emma')).toBeInTheDocument();
  });

  it('calls onEditClick when link is clicked', () => {
    const onClick = vi.fn();
    render(<ClassificationBar {...defaultProps} onEditClick={onClick} />);
    fireEvent.click(screen.getByText('Not right?'));
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});

describe('getMaterialTypeLabel', () => {
  it('returns correct label for known types', () => {
    expect(getMaterialTypeLabel('teacher_notes')).toBe('Teacher Notes');
    expect(getMaterialTypeLabel('past_exam')).toBe('Past Exam');
    expect(getMaterialTypeLabel('worksheet')).toBe('Worksheet');
  });

  it('returns "Document" for null', () => {
    expect(getMaterialTypeLabel(null)).toBe('Document');
  });

  it('returns "Document" for unknown type', () => {
    expect(getMaterialTypeLabel('something_else')).toBe('Document');
  });
});
