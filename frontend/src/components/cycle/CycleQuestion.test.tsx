/**
 * CycleQuestion — format-coverage tests (CB-TUTOR-002 #4069).
 *
 * Verifies that each of the three supported question formats renders the
 * expected UI shell — MCQ letters, T/F pair, and the fill-blank input.
 */
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { CycleQuestion } from './CycleQuestion';
import type { CycleQuestion as CycleQuestionType } from './types';

const baseQuestion: CycleQuestionType = {
  id: 'q-test',
  format: 'multiple_choice',
  question_text: 'What is 2 + 2?',
  options: ['3', '4', '5', '6'],
  correct_index: 1,
  explanation: 'Two plus two equals four.',
  reteach_snippet: 'Remember: 2 + 2 = 4.',
};

describe('CycleQuestion', () => {
  it('renders a multiple_choice question with A/B/C/D options', async () => {
    const onAnswer = vi.fn();
    render(
      <CycleQuestion question={baseQuestion} attempt={0} onAnswer={onAnswer} />,
    );

    // Prompt
    expect(screen.getByText('What is 2 + 2?')).toBeInTheDocument();
    // A/B/C/D letters
    expect(screen.getByText('A')).toBeInTheDocument();
    expect(screen.getByText('B')).toBeInTheDocument();
    expect(screen.getByText('C')).toBeInTheDocument();
    expect(screen.getByText('D')).toBeInTheDocument();
    // All four options present as radios
    expect(screen.getAllByRole('radio')).toHaveLength(4);

    await userEvent.click(screen.getByRole('radio', { name: /option b: 4/i }));
    expect(onAnswer).toHaveBeenCalledWith({ index: 1 });
  });

  it('renders a true_false question with exactly two buttons', async () => {
    const onAnswer = vi.fn();
    const tfQuestion: CycleQuestionType = {
      ...baseQuestion,
      id: 'q-tf',
      format: 'true_false',
      question_text: 'The sky is blue.',
      options: ['True', 'False'],
      correct_index: 0,
    };
    render(<CycleQuestion question={tfQuestion} attempt={0} onAnswer={onAnswer} />);

    expect(screen.getByText('The sky is blue.')).toBeInTheDocument();
    const radios = screen.getAllByRole('radio');
    expect(radios).toHaveLength(2);
    expect(screen.getByRole('radio', { name: 'True' })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: 'False' })).toBeInTheDocument();

    await userEvent.click(screen.getByRole('radio', { name: 'True' }));
    expect(onAnswer).toHaveBeenCalledWith({ index: 0 });
  });

  it('renders a fill_blank question with a text input and submit button', async () => {
    const onAnswer = vi.fn();
    const fillQuestion: CycleQuestionType = {
      ...baseQuestion,
      id: 'q-fill',
      format: 'fill_blank',
      question_text: 'The capital of France is ____.',
      options: ['Paris'],
      correct_index: 0,
    };
    render(
      <CycleQuestion question={fillQuestion} attempt={0} onAnswer={onAnswer} />,
    );

    expect(screen.getByText('The capital of France is ____.')).toBeInTheDocument();
    const input = screen.getByLabelText(/your answer/i);
    expect(input).toBeInTheDocument();
    const submit = screen.getByRole('button', { name: /submit answer/i });
    // Submit disabled until user types
    expect(submit).toBeDisabled();

    await userEvent.type(input, 'Paris');
    expect(submit).toBeEnabled();
    await userEvent.click(submit);
    expect(onAnswer).toHaveBeenCalledWith({ text: 'Paris' });
  });
});
