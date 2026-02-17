import { useTheme, type Theme } from '../context/ThemeContext';
import './ThemeToggle.css';

const THEME_META: Record<Theme, { icon: string; label: string }> = {
  light: { icon: '\u2600', label: 'Light' },
  dark: { icon: '\uD83C\uDF19', label: 'Dark' },
  focus: { icon: '\uD83C\uDF3F', label: 'Focus' },
};

export function ThemeToggle() {
  const { theme, cycleTheme } = useTheme();
  const meta = THEME_META[theme];

  return (
    <button
      className="theme-toggle"
      onClick={cycleTheme}
      title={`Theme: ${meta.label} (click to switch)`}
      aria-label={`Current theme: ${meta.label}. Click to switch.`}
    >
      <span className="theme-toggle-icon">{meta.icon}</span>
    </button>
  );
}
