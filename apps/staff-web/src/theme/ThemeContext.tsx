import { createContext, type PropsWithChildren, useContext, useEffect, useMemo, useState } from 'react';

export type ThemePreference = 'light' | 'dark' | 'system';
const ThemeContext = createContext<{ preference: ThemePreference; cycleTheme: () => void } | null>(null);
const THEME_KEY = 'staff-theme';

function readTheme(): ThemePreference {
  try {
    const value = localStorage.getItem(THEME_KEY);
    return value === 'light' || value === 'dark' ? value : 'system';
  } catch { return 'system'; }
}

export function ThemeProvider({ children }: PropsWithChildren) {
  const [preference, setPreference] = useState<ThemePreference>(readTheme);
  useEffect(() => {
    const media = matchMedia('(prefers-color-scheme: dark)');
    const apply = () => {
      const resolved = preference === 'system' ? (media.matches ? 'dark' : 'light') : preference;
      document.documentElement.dataset.theme = resolved;
      document.querySelector('meta[name="theme-color"]')?.setAttribute('content', resolved === 'dark' ? '#151715' : '#f3f0e9');
    };
    apply();
    media.addEventListener('change', apply);
    try { localStorage.setItem(THEME_KEY, preference); } catch { /* in-memory preference remains active */ }
    return () => media.removeEventListener('change', apply);
  }, [preference]);
  const value = useMemo(() => ({
    preference,
    cycleTheme: () => setPreference((current) => current === 'system' ? 'light' : current === 'light' ? 'dark' : 'system'),
  }), [preference]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const value = useContext(ThemeContext);
  if (!value) throw new Error('useTheme must be used inside ThemeProvider');
  return value;
}
