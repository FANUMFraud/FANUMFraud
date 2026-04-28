'use client';

import Link from 'next/link';
import type { Company } from '@/lib/api';
import { formatMomentumDelta, formatScore, getRiskLevel, momentumSymbol, momentumTone } from '@/lib/risk';
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

const sanctionsStyle = {
  listed: 'border-[var(--risk-high-rule)] bg-[var(--risk-high-bg)] text-[var(--risk-high)]',
  clear: 'border-[var(--risk-low-rule)] bg-[var(--risk-low-bg)] text-[var(--risk-low)]',
  unavailable: 'border-[var(--risk-medium-rule)] bg-[var(--risk-medium-bg)] text-[var(--risk-medium)]',
} as const;

function getSanctionsView(company: Company, locale: string) {
  if (company.sanctions?.is_sanctioned || company.sanctions?.status === 'listed') {
    return { label: locale === 'pl' ? 'Sankcje: na liście' : 'Sanctions: listed', className: sanctionsStyle.listed };
  }
  if (company.sanctions?.status === 'clear' || company.sanctions?.available === true) {
    return { label: locale === 'pl' ? 'Sankcje: brak wpisu' : 'Sanctions: clear', className: sanctionsStyle.clear };
  }
  return { label: locale === 'pl' ? 'Sankcje: nie sprawdzono' : 'Sanctions: not checked', className: sanctionsStyle.unavailable };
}

export default function CompanyCard({ company, animationDelay = 0 }: Props) {
  const { t, locale } = useI18n();
  const risk = getRiskLevel(company.current_score);
  const tone = riskTone[risk];
  const momentum = company.momentum_7d;
  const momentumDelta = momentum?.delta ?? 0;
  const momentumDirection = momentumTone(momentumDelta);
  const momentumStyle = {
    bad: 'border-[var(--risk-high-rule)] bg-[var(--risk-high-bg)] text-[var(--risk-high)]',
    neutral: 'border-[var(--border)] bg-[var(--surface-alt)] text-[var(--ink-muted)]',
    good: 'border-[var(--risk-low-rule)] bg-[var(--risk-low-bg)] text-[var(--risk-low)]',
  } as const;
  const labels = {
    high: t.card.riskHigh,
    medium: t.card.riskMedium,
    low: t.card.riskLow,
  } as const;
  const sanctions = getSanctionsView(company, locale);

  return (
    <Link
      href={`/companies/${company.id}`}
      className="no-underline block row-in"
      style={{ animationDelay: `${animationDelay}ms` }}
    >
      <article
        className="doc-card h-full flex flex-col transition-colors"
      >
        <div className="px-4 py-3 border-b border-[var(--rule)] bg-[var(--surface-alt)] flex items-start justify-between gap-3">
          <div className="flex items-start gap-3 min-w-0 flex-1">
            <span className={`mt-1 w-2.5 h-8 ${tone.swatch} shrink-0`} aria-hidden="true" />
            <div className="min-w-0">
              <p className="eyebrow mb-1">{locale === 'pl' ? 'Podmiot rejestru' : 'Registry entity'}</p>
              <h3 className="text-[16px] font-extrabold text-[var(--ink)] leading-snug truncate">
                {company.name}
              </h3>
              <div className="text-[11px] text-[var(--ink-muted)] font-mono mt-2 tnum flex flex-wrap gap-x-3 gap-y-1">
                <span>{t.card.nip}: {company.nip ?? '—'}</span>
                {company.ticker_gpw && (
                  <span className="text-[var(--ink-2)]">GPW: {company.ticker_gpw}</span>
                )}
              </div>
            </div>
          </div>
          <div className="shrink-0 flex flex-col items-end gap-1">
            <span
              className={`text-[10px] uppercase tracking-[0.12em] font-extrabold px-2 py-1 border ${tone.badge}`}
              style={{ borderRadius: 0 }}
            >
              {labels[risk]}
            </span>
            <span className={`text-[9px] uppercase tracking-[0.08em] font-extrabold px-2 py-0.5 border ${sanctions.className}`}>
              {sanctions.label}
            </span>
          </div>
        </div>

        <div className="p-4 flex-1 flex items-end justify-between gap-4">
          <div className="border-l-4 pl-3" style={{ borderColor: `var(--risk-${risk})` }}>
            <p className="eyebrow mb-2">{t.card.score}</p>
            <p className={`text-[44px] font-extrabold tnum tracking-tight leading-none ${tone.text}`}>
              {formatScore(company.current_score)}
              <span className="text-base font-medium text-[var(--ink-faint)] ml-1">
                {t.card.scoreOutOf}
              </span>
            </p>
          </div>
          {momentum && (
            <div className={`px-3 py-2 border text-right ${momentumStyle[momentumDirection]}`}>
              <p className="text-[10px] uppercase tracking-[0.1em] font-extrabold">
                {locale === 'pl' ? 'Trend 7d' : '7d trend'}
              </p>
              <p className="text-base font-extrabold tnum leading-none mt-1">
                {momentumSymbol(momentumDelta)} {formatMomentumDelta(momentumDelta)}
              </p>
            </div>
          )}
        </div>

        <div className="h-2 w-full bg-[var(--paper-2)] border-t border-[var(--rule)]">
          <div
            className={`h-full ${tone.bar} transition-[width] duration-700 ease-out`}
            style={{ width: `${Math.max(0, Math.min(100, company.current_score))}%` }}
          />
        </div>
      </article>
    </Link>
  );
}
