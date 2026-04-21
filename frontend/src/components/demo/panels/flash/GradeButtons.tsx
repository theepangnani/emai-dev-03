/**
 * GradeButtons — three self-grade buttons for the Flash Tutor short
 * learning cycle (#3786): Missed it / Almost / Got it.
 *
 * Colours come from brand tokens (coral for missed, amber for almost, green
 * for got it). No new palette.
 */

export type GradeValue = 'missed' | 'almost' | 'got_it';

export interface GradeButtonsProps {
  onGrade: (grade: GradeValue) => void;
  disabled?: boolean;
}

interface GradeDef {
  value: GradeValue;
  label: string;
  className: string;
  aria: string;
}

const GRADES: GradeDef[] = [
  {
    value: 'missed',
    label: 'Missed it',
    className: 'demo-flash-grade-btn demo-flash-grade-btn--missed',
    aria: 'Grade this card as missed',
  },
  {
    value: 'almost',
    label: 'Almost',
    className: 'demo-flash-grade-btn demo-flash-grade-btn--almost',
    aria: 'Grade this card as almost',
  },
  {
    value: 'got_it',
    label: 'Got it',
    className: 'demo-flash-grade-btn demo-flash-grade-btn--got-it',
    aria: 'Grade this card as got it',
  },
];

export function GradeButtons({ onGrade, disabled }: GradeButtonsProps) {
  return (
    <div
      className="demo-flash-grade-row"
      role="group"
      aria-label="Self-grade"
    >
      {GRADES.map((g) => (
        <button
          key={g.value}
          type="button"
          className={g.className}
          aria-label={g.aria}
          disabled={disabled}
          onClick={() => onGrade(g.value)}
        >
          {g.label}
        </button>
      ))}
    </div>
  );
}

export default GradeButtons;
