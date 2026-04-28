'use client';

import { useI18n } from '@/lib/i18n/I18nProvider';

export default function LocaleFade({ children }: { children: React.ReactNode }) {
  const { locale } = useI18n();
  return (
    <div key={locale} className="locale-fade">
      {children}
    </div>
  );
}
