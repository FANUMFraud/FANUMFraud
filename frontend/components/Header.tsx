'use client';

import Link from 'next/link';
import LanguageSwitcher from './LanguageSwitcher';
import ThemeSwitcher from './ThemeSwitcher';
import { useI18n } from '@/lib/i18n/I18nProvider';

interface Props {
  rightSlot?: React.ReactNode;
  leftSlot?: React.ReactNode;
}

export default function Header({ rightSlot, leftSlot }: Props) {
  const { locale } = useI18n();

  return (
    <header className="border-b border-[var(--border-strong)]">
      <div className="bg-[var(--brand-bg)] text-[var(--brand-fg)] border-b border-[var(--gov-blue)]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 min-h-9 flex items-center justify-between gap-4 text-[11px]">
          <span className="uppercase tracking-[0.16em] font-extrabold">
            {locale === 'pl' ? 'System oceny ryzyka AML' : 'AML risk assessment system'}
          </span>
          {rightSlot && (
            <div className="hidden md:flex items-center text-[var(--brand-fg)] opacity-85">
              {rightSlot}
            </div>
          )}
        </div>
      </div>

      <div className="bg-[var(--surface)]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-5 min-w-0">
            <Link
              href="/"
              className="no-underline flex items-center gap-4 group"
              aria-label="FanumFraud"
            >
              <span
                className="inline-flex items-center justify-center w-12 h-12 shrink-0 border-2 text-[var(--accent-fg)] font-black tracking-tight"
                style={{ background: 'var(--gov-blue)', borderColor: 'var(--gov-blue)' }}
              >
                FF
              </span>
              <span className="flex flex-col leading-tight">
                <span className="text-[11px] uppercase tracking-[0.16em] text-[var(--ink-muted)] font-extrabold">
                  {locale === 'pl' ? 'Centralny rejestr' : 'Central registry'}
                </span>
                <span className="font-extrabold tracking-tight text-xl text-[var(--ink)]">
                  FanumFraud
                </span>
                <span className="hidden sm:block text-[12px] text-[var(--ink-muted)] mt-0.5">
                  {locale === 'pl' ? 'Ocena reputacji i ryzyka podmiotow gospodarczych' : 'Entity reputation and risk assessment'}
                </span>
              </span>
            </Link>
            {leftSlot && (
              <div className="hidden lg:flex items-center min-w-0 pl-5 border-l border-[var(--border)] h-12">
                {leftSlot}
              </div>
            )}
          </div>

          <div className="flex items-center gap-2.5">
            <ThemeSwitcher />
            <LanguageSwitcher />
          </div>
        </div>
        {leftSlot && (
          <div className="lg:hidden border-t border-[var(--rule)] px-4 sm:px-6 py-2">
            {leftSlot}
          </div>
        )}
      </div>
    </header>
  );
}
