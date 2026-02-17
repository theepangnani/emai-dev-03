import { useTheme, type Theme } from '../context/ThemeContext';
import './ThemeToggle.css';

const THEME_META: Record<Theme, { icon: string; label: string }> = {
  light: { icon: '\u2600', label: 'Light' },
  dark: { icon: '\uD83C\uDF19', label: 'Dark' },
  focus: { icon: '\uD83C\uDF3F', label: 'Focus' },
};

export function ThemeToggle() {
  const { theme, cycleTheme, style, toggleStyle } = useTheme();
  const meta = THEME_META[theme];

  return (
    <div className="theme-controls">
      <button
        className="theme-toggle"
        onClick={cycleTheme}
        title={`Theme: ${meta.label} (click to switch)`}
        aria-label={`Current theme: ${meta.label}. Click to switch.`}
      >
        <span className="theme-toggle-icon">{meta.icon}</span>
      </button>
      <button
        className={`style-toggle${style === 'gradient' ? ' active' : ''}`}
        onClick={toggleStyle}
        title={`Style: ${style === 'flat' ? 'Flat' : 'Gradient'} (click to switch)`}
        aria-label={`Current style: ${style}. Click to switch.`}
      >
        <span className="style-toggle-icon">{style === 'gradient' ? '\u25C6' : '\u25C7'}</span>
      </button>
    </div>
  );
}
