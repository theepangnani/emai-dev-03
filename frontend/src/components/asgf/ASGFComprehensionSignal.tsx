/**
 * ASGFComprehensionSignal — Binary "Got it / Still confused" signal component.
 *
 * Renders two buttons at the bottom of each slide. On click, fires a callback
 * with the slide number and the signal type. The selected button stays
 * highlighted and the other dims. Disabled state while re-explanation is
 * generating.
 *
 * Issue: #3399
 */
import { useState } from 'react';

import './ASGFComprehensionSignal.css';

export type ComprehensionSignalType = 'got_it' | 'still_confused';

export interface ComprehensionSignalPayload {
  slideNumber: number;
  signal: ComprehensionSignalType;
}

interface Props {
  slideNumber: number;
  onSignal: (payload: ComprehensionSignalPayload) => void;
  /** True while a re-explanation is being generated */
  loading?: boolean;
  /** Disable the buttons entirely (e.g. while navigating) */
  disabled?: boolean;
  /** Restore previously-selected signal when the component re-mounts on slide navigation */
  initialSignal?: ComprehensionSignalType | null;
}

export default function ASGFComprehensionSignal({
  slideNumber,
  onSignal,
  loading = false,
  disabled = false,
  initialSignal = null,
}: Props) {
  const [selected, setSelected] = useState<ComprehensionSignalType | null>(initialSignal);

  const handleClick = (signal: ComprehensionSignalType) => {
    if (disabled || loading) return;
    setSelected(signal);
    onSignal({ slideNumber, signal });
  };

  const isDisabled = disabled || loading;

  const gotItClasses = [
    'asgf-comprehension-signal__btn',
    'asgf-comprehension-signal__btn--got-it',
    selected === 'got_it' ? 'asgf-comprehension-signal__btn--selected' : '',
    selected && selected !== 'got_it' ? 'asgf-comprehension-signal__btn--dimmed' : '',
  ]
    .filter(Boolean)
    .join(' ');

  const confusedClasses = [
    'asgf-comprehension-signal__btn',
    'asgf-comprehension-signal__btn--confused',
    selected === 'still_confused' ? 'asgf-comprehension-signal__btn--selected' : '',
    selected && selected !== 'still_confused' ? 'asgf-comprehension-signal__btn--dimmed' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className="asgf-comprehension-signal">
      <button
        type="button"
        className={gotItClasses}
        disabled={isDisabled}
        onClick={() => handleClick('got_it')}
        aria-label="Got it"
      >
        <span aria-hidden="true">&#x2713;</span>
        Got it
      </button>

      <button
        type="button"
        className={confusedClasses}
        disabled={isDisabled}
        onClick={() => handleClick('still_confused')}
        aria-label="Still confused"
      >
        {loading && selected === 'still_confused' ? (
          <span className="asgf-comprehension-signal__spinner" aria-hidden="true" />
        ) : (
          <span aria-hidden="true">?</span>
        )}
        {loading && selected === 'still_confused' ? 'Generating...' : 'Still confused'}
      </button>
    </div>
  );
}
