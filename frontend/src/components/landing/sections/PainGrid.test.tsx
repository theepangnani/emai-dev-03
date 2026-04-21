import { render, screen } from '@testing-library/react';
import { PainGrid, section } from './PainGrid';

describe('PainGrid (CB-LAND-001 S4)', () => {
  it('renders 4 role-quote cards and the demo CTA button', () => {
    render(<PainGrid />);

    // Kicker + headline (with italicized <em>broken.</em>).
    expect(screen.getByText('Sound familiar?')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent(
      'School communication is broken.',
    );

    // 4 cards — verified via the 4 role badges + 4 quote texts.
    expect(screen.getByText('Parent')).toBeInTheDocument();
    expect(screen.getByText('Student')).toBeInTheDocument();
    expect(screen.getByText('Teacher')).toBeInTheDocument();
    expect(screen.getByText('Admin')).toBeInTheDocument();

    expect(screen.getAllByRole('listitem')).toHaveLength(4);

    expect(screen.getByText(/I miss half my kid's emails/)).toBeInTheDocument();
    expect(screen.getByText(/I re-read chapters and still forget/)).toBeInTheDocument();
    expect(screen.getByText(/Parents never see my announcements/)).toBeInTheDocument();
    expect(screen.getByText(/No visibility across homes/)).toBeInTheDocument();

    // "Better way" strip + CTA button.
    expect(screen.getByText(/There.s a better way\./)).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /Try the 30-second demo/i }),
    ).toBeInTheDocument();
  });

  it('exports a glob-registry section contract', () => {
    expect(section).toEqual({ id: 'pain', order: 20, component: PainGrid });
  });
});
