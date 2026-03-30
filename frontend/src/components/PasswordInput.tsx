import { useState } from 'react';
import './PasswordInput.css';

interface PasswordInputProps {
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  placeholder?: string;
  name?: string;
  id?: string;
  required?: boolean;
  autoComplete?: string;
  minLength?: number;
  disabled?: boolean;
  'aria-describedby'?: string;
  'aria-invalid'?: boolean | 'true' | 'false';
  'aria-required'?: boolean | 'true' | 'false';
}

export function PasswordInput({
  value,
  onChange,
  placeholder = '••••••••',
  name,
  id,
  required,
  autoComplete,
  minLength,
  disabled,
  'aria-describedby': ariaDescribedby,
  'aria-invalid': ariaInvalid,
  'aria-required': ariaRequired,
}: PasswordInputProps) {
  const [visible, setVisible] = useState(false);

  return (
    <div className="password-input-wrapper">
      <input
        type={visible ? 'text' : 'password'}
        id={id}
        name={name}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        required={required}
        autoComplete={autoComplete}
        minLength={minLength}
        disabled={disabled}
        aria-describedby={ariaDescribedby}
        aria-invalid={ariaInvalid}
        aria-required={ariaRequired}
      />
      <button
        type="button"
        className="password-toggle-btn"
        onClick={() => setVisible(!visible)}
        aria-label={visible ? 'Hide password' : 'Show password'}
      >
        {visible ? (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
            <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
            <line x1="1" y1="1" x2="23" y2="23"/>
          </svg>
        ) : (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
            <circle cx="12" cy="12" r="3"/>
          </svg>
        )}
      </button>
    </div>
  );
}
