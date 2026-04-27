'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import {
  DEFAULT_LOCALE,
  DICTIONARIES,
  LOCALES,
  type Dictionary,
  type Locale,
} from './dictionaries';

type I18nContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: Dictionary;
  formatDate: (date: Date | string, opts?: Intl.DateTimeFormatOptions) => string;
  formatTime: (date: Date | string, opts?: Intl.DateTimeFormatOptions) => string;
};

const I18nContext = createContext<I18nContextValue | null>(null);

const STORAGE_KEY = 'fanumfraud:locale';
const DATE_LOCALE: Record<Locale, string> = { pl: 'pl-PL', en: 'en-GB' };

function isLocale(value: unknown): value is Locale {
  return typeof value === 'string' && (LOCALES as readonly string[]).includes(value);
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (isLocale(stored)) {
      setLocaleState(stored);
      document.documentElement.lang = stored;
    }
  }, []);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    window.localStorage.setItem(STORAGE_KEY, next);
    document.documentElement.lang = next;
  }, []);

  const value = useMemo<I18nContextValue>(() => {
    const tag = DATE_LOCALE[locale];
    return {
      locale,
      setLocale,
      t: DICTIONARIES[locale],
      formatDate: (date, opts) => {
        const d = typeof date === 'string' ? new Date(date) : date;
        return d.toLocaleDateString(tag, opts ?? { day: '2-digit', month: 'long', year: 'numeric' });
      },
      formatTime: (date, opts) => {
        const d = typeof date === 'string' ? new Date(date) : date;
        return d.toLocaleTimeString(tag, opts ?? { hour: '2-digit', minute: '2-digit' });
      },
    };
  }, [locale, setLocale]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error('useI18n must be used within <I18nProvider>');
  return ctx;
}
