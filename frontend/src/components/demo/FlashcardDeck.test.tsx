import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { FlashcardDeck } from './FlashcardDeck';

const THREE_CARDS = JSON.stringify([
  { front: 'What is a cell?', back: 'The smallest living unit.' },
  { front: 'What does the nucleus do?', back: 'Controls cell activities.' },
  { front: 'What do mitochondria do?', back: 'Release energy from food.' },
]);

describe('FlashcardDeck — parsing', () => {
  it('parses a valid 3-card JSON array and renders 1 / 3 with first card front', () => {
    render(<FlashcardDeck rawText={THREE_CARDS} />);
    expect(screen.getByText('1 / 3')).toBeInTheDocument();
    expect(screen.getByText('What is a cell?')).toBeInTheDocument();
  });

  it('strips the trailing demo-preview footer before parsing', () => {
    const withFooter = `${THREE_CARDS}\nThis is a ClassBridge demo preview.`;
    render(<FlashcardDeck rawText={withFooter} />);
    expect(screen.getByText('1 / 3')).toBeInTheDocument();
    expect(screen.getByText('What is a cell?')).toBeInTheDocument();
  });

  it('strips ```json ... ``` fences before parsing', () => {
    const fenced = '```json\n' + THREE_CARDS + '\n```';
    render(<FlashcardDeck rawText={fenced} />);
    expect(screen.getByText('1 / 3')).toBeInTheDocument();
    expect(screen.getByText('What is a cell?')).toBeInTheDocument();
  });

  it('renders fallback <pre> when JSON is invalid', () => {
    const bad = 'not valid json at all { [ }';
    const { container } = render(<FlashcardDeck rawText={bad} />);
    const pre = container.querySelector('pre.demo-flashcard-fallback');
    expect(pre).not.toBeNull();
    expect(pre).toHaveTextContent('not valid json at all');
    expect(screen.queryByRole('region', { name: /flashcards/i })).not.toBeInTheDocument();
  });
});

describe('FlashcardDeck — interaction', () => {
  it('toggles front <-> back on card click and flips aria-expanded', async () => {
    const user = userEvent.setup();
    render(<FlashcardDeck rawText={THREE_CARDS} />);
    const cardBtn = screen.getByRole('button', { name: /show card back/i });
    expect(cardBtn).toHaveAttribute('aria-expanded', 'false');
    expect(screen.getByText('What is a cell?')).toBeInTheDocument();

    await user.click(cardBtn);

    const flippedBtn = screen.getByRole('button', { name: /show card front/i });
    expect(flippedBtn).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText('The smallest living unit.')).toBeInTheDocument();
    expect(screen.queryByText('What is a cell?')).not.toBeInTheDocument();

    await user.click(flippedBtn);
    expect(screen.getByRole('button', { name: /show card back/i })).toHaveAttribute(
      'aria-expanded',
      'false',
    );
    expect(screen.getByText('What is a cell?')).toBeInTheDocument();
  });

  it('ArrowRight advances to card 2 and resets flip state to front', async () => {
    const user = userEvent.setup();
    render(<FlashcardDeck rawText={THREE_CARDS} />);

    await user.click(screen.getByRole('button', { name: /show card back/i }));
    expect(screen.getByText('The smallest living unit.')).toBeInTheDocument();

    const region = screen.getByRole('region', { name: /flashcards/i });
    region.focus();
    await user.keyboard('{ArrowRight}');

    expect(screen.getByText('2 / 3')).toBeInTheDocument();
    expect(screen.getByText('What does the nucleus do?')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /show card back/i })).toHaveAttribute(
      'aria-expanded',
      'false',
    );
  });

  it('ArrowLeft on card 1 keeps counter at 1 / 3 (prev disabled)', async () => {
    const user = userEvent.setup();
    render(<FlashcardDeck rawText={THREE_CARDS} />);

    const prevBtn = screen.getByRole('button', { name: /previous card/i });
    expect(prevBtn).toBeDisabled();

    const region = screen.getByRole('region', { name: /flashcards/i });
    region.focus();
    await user.keyboard('{ArrowLeft}');

    expect(screen.getByText('1 / 3')).toBeInTheDocument();
    expect(screen.getByText('What is a cell?')).toBeInTheDocument();
  });
});

describe('FlashcardDeck — streaming placeholder', () => {
  it('renders the "Building your flashcards" placeholder and no cards when streaming', () => {
    render(<FlashcardDeck rawText={THREE_CARDS} isStreaming />);
    expect(screen.getByText(/building your flashcards/i)).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: /flashcards/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /previous card/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /next card/i })).not.toBeInTheDocument();
    expect(screen.queryByText('1 / 3')).not.toBeInTheDocument();
  });
});
