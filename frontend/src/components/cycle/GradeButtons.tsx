/**
 * GradeButtons — three self-grade buttons for the Learning Cycle
 * (CB-TUTOR-002 #4069).
 *
 * Lifted from `components/demo/panels/flash/GradeButtons.tsx`. Demo original
 * kept in place.
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
    className: 'cycle-grade-btn cycle-grade-btn--missed',
    aria: 'Grade this card as missed',
  },
  {
    value: 'almost',
    label: 'Almost',
    className: 'cycle-grade-btn cycle-grade-btn--almost',
    aria: 'Grade this card as almost',
  },
  {
    value: 'got_it',
    label: 'Got it',
    className: 'cycle-grade-btn cycle-grade-btn--got-it',
    aria: 'Grade this card as got it',
  },
];

export function GradeButtons({ onGrade, disabled }: GradeButtonsProps) {
  return (
    <div className="cycle-grade-row" role="group" aria-label="Self-grade">
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
