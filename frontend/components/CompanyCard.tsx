'use client';

import Link from 'next/link';
import type { Company } from '@/lib/api';
import { getRiskLevel } from '@/lib/risk';
import { useI18n } from '@/lib/i18n/I18nProvider';

interface Props {
  company: Company;
  animationDelay?: number;
}

const riskTone = {
  high: {
    swatch: 'bg-[var(--risk-high)]',
    text: 'text-[var(--risk-high)]',
    badge: 'bg-[var(--risk-high-bg)] text-[var(--risk-high)] border-[var(--risk-high-rule)]',
    bar: 'bg-[var(--risk-high)]',
  },
  medium: {
    swatch: 'bg-[var(--risk-medium)]',
    text: 'text-[var(--risk-medium)]',
    badge: 'bg-[var(--risk-medium-bg)] text-[var(--risk-medium)] border-[var(--risk-medium-rule)]',
    bar: 'bg-[var(--risk-medium)]',
  },
  low: {
    swatch: 'bg-[var(--risk-low)]',
    text: 'text-[var(--risk-low)]',
    badge: 'bg-[var(--risk-low-bg)] text-[var(--risk-low)] border-[var(--risk-low-rule)]',
    bar: 'bg-[var(--risk-low)]',
  },
} as const;

export default function CompanyCard({ company, animationDelay = 0 }: Props) {
  const { t } = useI18n();
  const risk = getRiskLevel(company.current_score);
  const tone = riskTone[risk];
  const labels = {
    high: t.card.riskHigh,
    medium: t.card.riskMedium,
    low: t.card.riskLow,
  } as const;

  return (
    <Link
      href={`/companies/${company.id}`}
      className="no-underline block row-in"
      style={{ animationDelay: `${animationDelay}ms` }}
    >
      <article
        className="doc-card h-full p-5 flex flex-col gap-4 transition-colors hover:border-[var(--ink)]"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3 min-w-0 flex-1">
            <span className={`mt-1.5 w-2 h-2 ${tone.swatch} shrink-0`} aria-hidden="true" />
            <div className="min-w-0">
              <h3 className="text-[15px] font-semibold text-[var(--ink)] leading-snug truncate">
                {company.name}
              </h3>
              <p className="text-[11px] text-[var(--ink-muted)] font-mono mt-1 tnum">
                {t.card.nip}: {company.nip ?? '—'}
              </p>
            </div>
          </div>
          <span
            className={`shrink-0 text-[10px] uppercase tracking-[0.12em] font-semibold px-2 py-0.5 border ${tone.badge}`}
            style={{ borderRadius: '2px' }}
          >
            {labels[risk]}
          </span>
        </div>

        <hr className="hr-rule" />

        <div className="flex items-end justify-between gap-3">
          <div>
            <p className="eyebrow mb-1">{t.card.score}</p>
            <p className={`text-[42px] font-semibold tnum tracking-tight leading-none ${tone.text}`}>
              {company.current_score}
              <span className="text-base font-medium text-[var(--ink-faint)] ml-1">
                {t.card.scoreOutOf}
              </span>
            </p>
          </div>
        </div>

        <div className="h-1 w-full bg-[var(--paper-2)] border-t border-[var(--rule)]">
          <div
            className={`h-full ${tone.bar} transition-[width] duration-700 ease-out`}
            style={{ width: `${company.current_score}%` }}
          />
        </div>
      </article>
    </Link>
  );
}
