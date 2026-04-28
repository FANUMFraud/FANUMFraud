'use client';

import { useTheme, type Theme } from '@/lib/theme/ThemeProvider';
import { useI18n } from '@/lib/i18n/I18nProvider';

const THEMES: ReadonlyArray<Theme> = ['light', 'dark'];

function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
      <circle cx="12" cy="12" r="3.5" />
      <path strokeLinecap="round" d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M5.6 18.4l1.4-1.4M17 7l1.4-1.4" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" />
    </svg>
  );
}

export default function ThemeSwitcher() {
  const { theme, setTheme } = useTheme();
  const { locale } = useI18n();
  const activeIndex = THEMES.indexOf(theme);
  const ariaLabel = locale === 'pl' ? 'Motyw' : 'Theme';

  return (
    <div
      role="group"
      aria-label={ariaLabel}
      className="pill-switch theme-switch"
      data-active-index={activeIndex}
    >
      <span className="pill-switch__indicator" aria-hidden="true" />
      {THEMES.map((t) => {
        const active = t === theme;
        const label =
          t === 'light'
            ? locale === 'pl' ? 'Jasny motyw' : 'Light theme'
            : locale === 'pl' ? 'Ciemny motyw' : 'Dark theme';
        return (
          <button
            key={t}
            type="button"
            onClick={() => setTheme(t)}
            aria-pressed={active}
            aria-label={label}
            title={label}
            className="pill-switch__btn"
          >
            {t === 'light' ? <SunIcon /> : <MoonIcon />}
          </button>
        );
      })}
    </div>
  );
}
