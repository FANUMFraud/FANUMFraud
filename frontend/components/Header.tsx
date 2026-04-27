'use client';

import Link from 'next/link';
import Image from 'next/image';
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
    <header>
      <div className="h-[3px] w-full" style={{ background: 'var(--crimson)' }} aria-hidden="true" />

      <div className="bg-[var(--surface)] border-b border-[var(--border)]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
          <div className="flex items-center gap-5 min-w-0">
            <Link
              href="/"
              className="no-underline flex items-center gap-3 group"
              aria-label="FanumFraud"
            >
              <span
                className="inline-flex items-center justify-center w-9 h-9 overflow-hidden"
                style={{ background: '#000000' }}
              >
                <Image
                  src="/assets/favicon/android-chrome-192x192.png"
                  alt=""
                  width={36}
                  height={36}
                  priority
                  aria-hidden="true"
                />
              </span>
              <span className="flex flex-col leading-tight">
                <span className="text-[10px] uppercase tracking-[0.18em] text-[var(--ink-muted)]">
                  {locale === 'pl' ? 'Rejestr' : 'Registry'}
                </span>
                <span className="font-semibold tracking-tight text-[15px] text-[var(--ink)]">
                  FanumFraud
                </span>
              </span>
            </Link>
            {leftSlot && (
              <div className="hidden sm:flex items-center min-w-0 pl-5 border-l border-[var(--border)] h-9">
                {leftSlot}
              </div>
            )}
          </div>

          <div className="flex items-center gap-2.5">
            {rightSlot && (
              <div className="hidden md:flex items-center text-[11px] text-[var(--ink-muted)] mr-1">
                {rightSlot}
              </div>
            )}
            <ThemeSwitcher />
            <LanguageSwitcher />
          </div>
        </div>
      </div>
    </header>
  );
}
