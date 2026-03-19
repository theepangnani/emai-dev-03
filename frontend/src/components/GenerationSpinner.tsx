import './GenerationSpinner.css';

interface GenerationSpinnerProps {
  /** sm = 14px, md = 18px, lg = 36px */
  size?: 'sm' | 'md' | 'lg';
  /** Optional pulsing text label */
  label?: string;
}

export function GenerationSpinner({ size = 'md', label }: GenerationSpinnerProps) {
  if (label) {
    return (
      <span className="gen-spinner-row">
        <span className={`gen-spinner gen-spinner--${size}`} aria-hidden="true" />
        <span className="gen-spinner-label">{label}</span>
      </span>
    );
  }

  return <span className={`gen-spinner gen-spinner--${size}`} aria-hidden="true" />;
}
