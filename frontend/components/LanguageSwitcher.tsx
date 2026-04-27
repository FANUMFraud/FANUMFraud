'use client';

import { LOCALES, type Locale } from '@/lib/i18n/dictionaries';
import { useI18n } from '@/lib/i18n/I18nProvider';

const SHORT: Record<Locale, string> = { pl: 'PL', en: 'EN' };

export default function LanguageSwitcher() {
  const { locale, setLocale, t } = useI18n();
  const activeIndex = LOCALES.indexOf(locale);

  return (
    <div
      role="group"
      aria-label={t.nav.languageLabel}
      className="pill-switch lang-switch"
      data-active-index={activeIndex}
    >
      <span className="pill-switch__indicator" aria-hidden="true" />
      {LOCALES.map((code) => {
        const active = code === locale;
        return (
          <button
            key={code}
            type="button"
            onClick={() => setLocale(code)}
            aria-pressed={active}
            className="pill-switch__btn"
          >
            {SHORT[code]}
          </button>
        );
      })}
    </div>
  );
}
