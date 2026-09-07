import { useTheme } from '../theme/ThemeContext';

const labels = { system: 'Sistema', light: 'Claro', dark: 'Oscuro' } as const;

export function ThemeButton() {
  const { preference, cycleTheme } = useTheme();
  return (
    <button className="theme-button" type="button" onClick={cycleTheme} aria-label={`Tema: ${labels[preference]}. Cambiar tema`}>
      <span aria-hidden="true">{preference === 'dark' ? '☾' : preference === 'light' ? '☀' : '◐'}</span>
      <span>{labels[preference]}</span>
    </button>
  );
}
