/**
 * Regression tests for #4020 — render true_false and fill_blank
 * quiz question types in the ASGF slide-anchored quiz bridge.
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect } from 'vitest';
import { ASGFQuizBridge } from './ASGFQuizBridge';
import type { ASGFQuizQuestion } from '../../api/asgf';

const baseMCQ: ASGFQuizQuestion = {
  question_text: 'What is 2 + 2?',
  options: ['3', '4', '5', '6'],
  correct_index: 1,
  bloom_tier: 'recall',
  slide_reference: 0,
  hint_text: 'Look at slide 1',
  explanation: 'Two plus two equals four.',
};

describe('ASGFQuizBridge — #4020 true_false + fill_blank rendering', () => {
  it('true_false: renders 2 buttons (True / False) and selecting True marks correct', async () => {
    const question: ASGFQuizQuestion = {
      question_text: 'The sky is blue.',
      options: ['True', 'False'],
      correct_index: 0,
      bloom_tier: 'recall',
      slide_reference: 0,
      hint_text: 'Look outside.',
      explanation: 'On a clear day, the sky appears blue.',
      format: 'true_false',
    };

    render(
      <ASGFQuizBridge questions={[question]} sessionId="s-1" />,
    );

    // Question shows
    expect(screen.getByText('The sky is blue.')).toBeInTheDocument();

    // Two radio buttons labelled True and False
    const trueBtn = screen.getByRole('radio', { name: 'True' });
    const falseBtn = screen.getByRole('radio', { name: 'False' });
    expect(trueBtn).toBeInTheDocument();
    expect(falseBtn).toBeInTheDocument();
    expect(screen.getByRole('radiogroup', { name: 'True or False' })).toBeInTheDocument();

    // No A/B/C/D letter badges rendered
    expect(screen.queryByText('A')).not.toBeInTheDocument();

    // Click True → explanation / Next button appears (correct path)
    const user = userEvent.setup();
    await user.click(trueBtn);

    await waitFor(() => {
      expect(screen.getByText('Why correct')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /see results/i })).toBeInTheDocument();
  });

  it('fill_blank: renders input + submit, typing correct answer marks correct', async () => {
    const question: ASGFQuizQuestion = {
      question_text: 'The capital of France is ____.',
      options: ['Paris', '', '', ''],
      correct_index: 0,
      bloom_tier: 'recall',
      slide_reference: 0,
      hint_text: 'Think of the Eiffel Tower.',
      explanation: 'Paris is the capital of France.',
      format: 'fill_blank',
    };

    render(
      <ASGFQuizBridge questions={[question]} sessionId="s-2" />,
    );

    expect(screen.getByText('The capital of France is ____.')).toBeInTheDocument();

    // Input with label
    const input = screen.getByLabelText(/your answer/i) as HTMLInputElement;
    expect(input).toBeInTheDocument();
    expect(input.tagName).toBe('INPUT');

    // No A/B/C/D letter badges and no radiogroup
    expect(screen.queryByRole('radiogroup')).not.toBeInTheDocument();

    const user = userEvent.setup();
    await user.type(input, 'Paris');
    await user.click(screen.getByRole('button', { name: /submit answer/i }));

    await waitFor(() => {
      expect(screen.getByText('Why correct')).toBeInTheDocument();
    });
    // Typed answer is echoed back for clarity
    expect(screen.getByText('Paris')).toBeInTheDocument();
  });

  it('multiple_choice (default, no format field): still renders A/B/C/D (regression)', async () => {
    render(
      <ASGFQuizBridge questions={[baseMCQ]} sessionId="s-3" />,
    );
    expect(screen.getByRole('radio', { name: /Option A: 3/ })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /Option B: 4/ })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /Option C: 5/ })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /Option D: 6/ })).toBeInTheDocument();
  });
});
