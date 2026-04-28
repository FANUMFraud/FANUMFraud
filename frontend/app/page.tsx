'use client';

import { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { getCompanies, type Company } from '@/lib/api';
import CompanyCard from '@/components/CompanyCard';
import SearchBar from '@/components/SearchBar';
import Header from '@/components/Header';
import LocaleFade from '@/components/LocaleFade';
import { formatMomentumDelta, formatScore, getRiskLevel, momentumSymbol, momentumTone } from '@/lib/risk';
import { useI18n } from '@/lib/i18n/I18nProvider';

type SortMode = 'risk_desc' | 'risk_asc' | 'trend_desc' | 'name';

function isDemoCompany(company: Company): boolean {
  return Boolean(company.nip?.startsWith('10100000'));
}

const riskBadgeClass = {
  high: 'border-[var(--risk-high-rule)] bg-[var(--risk-high-bg)] text-[var(--risk-high)]',
  medium: 'border-[var(--risk-medium-rule)] bg-[var(--risk-medium-bg)] text-[var(--risk-medium)]',
  low: 'border-[var(--risk-low-rule)] bg-[var(--risk-low-bg)] text-[var(--risk-low)]',
} as const;

const momentumBadgeClass = {
  bad: 'border-[var(--risk-high-rule)] bg-[var(--risk-high-bg)] text-[var(--risk-high)]',
  neutral: 'border-[var(--border)] bg-[var(--surface-alt)] text-[var(--ink-muted)]',
  good: 'border-[var(--risk-low-rule)] bg-[var(--risk-low-bg)] text-[var(--risk-low)]',
} as const;

const sanctionsBadgeClass = {
  listed: riskBadgeClass.high,
  clear: 'border-[var(--risk-low-rule)] bg-[var(--risk-low-bg)] text-[var(--risk-low)]',
  unavailable: 'border-[var(--risk-medium-rule)] bg-[var(--risk-medium-bg)] text-[var(--risk-medium)]',
} as const;

const nipBadgeClass = {
  valid: 'border-[var(--risk-low-rule)] bg-[var(--risk-low-bg)] text-[var(--risk-low)]',
  invalid: 'border-[var(--risk-high-rule)] bg-[var(--risk-high-bg)] text-[var(--risk-high)]',
  missing: 'border-[var(--risk-medium-rule)] bg-[var(--risk-medium-bg)] text-[var(--risk-medium)]',
} as const;

const evidenceBadgeClass = {
  high: 'border-[var(--risk-low-rule)] bg-[var(--risk-low-bg)] text-[var(--risk-low)]',
  medium: 'border-[var(--risk-medium-rule)] bg-[var(--risk-medium-bg)] text-[var(--risk-medium)]',
  low: 'border-[var(--border)] bg-[var(--surface-alt)] text-[var(--ink-muted)]',
} as const;

function sanctionsStatus(company: Company, locale: string): { label: string; className: string } {
  if (company.sanctions?.is_sanctioned || company.sanctions?.status === 'listed') {
    return { label: locale === 'pl' ? 'Na liście' : 'Listed', className: sanctionsBadgeClass.listed };
  }
  if (company.sanctions?.status === 'clear' || company.sanctions?.available === true) {
    return { label: locale === 'pl' ? 'Brak wpisu' : 'Clear', className: sanctionsBadgeClass.clear };
  }
  return { label: locale === 'pl' ? 'Nie sprawdzono' : 'Not checked', className: sanctionsBadgeClass.unavailable };
}

function nipStatus(company: Company, locale: string): { label: string; className: string } {
  const status = company.nip_check?.status ?? (company.nip ? 'invalid' : 'missing');
  if (status === 'valid') {
    return { label: locale === 'pl' ? 'NIP OK' : 'NIP OK', className: nipBadgeClass.valid };
  }
  if (status === 'invalid') {
    return { label: locale === 'pl' ? 'NIP błędny' : 'NIP invalid', className: nipBadgeClass.invalid };
  }
  return { label: locale === 'pl' ? 'Brak NIP' : 'NIP missing', className: nipBadgeClass.missing };
}

function evidenceStatus(company: Company, locale: string): { label: string; className: string } {
  const level = company.evidence_quality?.level === 'high' || company.evidence_quality?.level === 'medium'
    ? company.evidence_quality.level
    : 'low';
  const score = company.evidence_quality?.score ?? 0;
  const label = locale === 'pl'
    ? `Dowody ${level === 'high' ? 'wys.' : level === 'medium' ? 'śr.' : 'nis.'} ${score.toFixed(0)}`
    : `Evidence ${level} ${score.toFixed(0)}`;
  return { label, className: evidenceBadgeClass[level] };
}

type DemoScenario = {
  key: string;
  title: string;
  description: string;
  company?: Company;
  tone: 'high' | 'medium' | 'low';
};

function pickDemoScenarios(companies: Company[], locale: string): DemoScenario[] {
  const withHistory = companies.filter((company) => company.momentum_7d || company.momentum_30d);
  const sanctioned = companies.find((company) => company.sanctions?.is_sanctioned || company.sanctions?.status === 'listed');
  const worst = [...withHistory].sort((a, b) => a.current_score - b.current_score)[0];
  const clean = [...withHistory]
    .filter((company) => !company.sanctions?.is_sanctioned)
    .sort((a, b) => b.current_score - a.current_score)[0];
  const declining = [...withHistory].sort((a, b) => (a.momentum_7d?.delta ?? 0) - (b.momentum_7d?.delta ?? 0))[0];

  const scenarios: DemoScenario[] = [
    {
      key: 'sanctions',
      title: locale === 'pl' ? 'Sankcje i blokada' : 'Sanctions and block',
      description: locale === 'pl' ? 'Pokazuje twardy sygnał compliance i rekomendację BLOCK.' : 'Shows a hard compliance signal and BLOCK recommendation.',
      company: sanctioned,
      tone: 'high',
    },
    {
      key: 'shock',
      title: locale === 'pl' ? 'Szok reputacyjny' : 'Reputation shock',
      description: locale === 'pl' ? 'Najgorszy scoring w rejestrze i materiały dowodowe.' : 'Worst score in the registry with supporting evidence.',
      company: worst,
      tone: 'high',
    },
    {
      key: 'trend',
      title: locale === 'pl' ? 'Trend 7 dni' : '7-day trend',
      description: locale === 'pl' ? 'Firma z największym pogorszeniem lub zmianą momentum.' : 'Company with the strongest deterioration or momentum change.',
      company: declining,
      tone: 'medium',
    },
    {
      key: 'clean',
      title: locale === 'pl' ? 'Czysty baseline' : 'Clean baseline',
      description: locale === 'pl' ? 'Wysoki scoring, brak sankcji, rekomendacja PROCEED.' : 'High score, no sanctions, PROCEED recommendation.',
      company: clean,
      tone: 'low',
    },
  ];
  return scenarios.filter((scenario) => scenario.company);
}

interface RegistrySectionProps {
  title: string;
  companies: Company[];
  locale: string;
  nipLabel: string;
  riskLabels: Readonly<Record<'high' | 'medium' | 'low', string>>;
  animationOffset?: number;
}

function RegistrySection({ title, companies, locale, nipLabel, riskLabels, animationOffset = 0 }: RegistrySectionProps) {
  const labels = {
    entity: locale === 'pl' ? 'Podmiot' : 'Entity',
    source: locale === 'pl' ? 'Źródło' : 'Source',
    stock: 'GPW',
    score: locale === 'pl' ? 'Score' : 'Score',
    risk: locale === 'pl' ? 'Ryzyko' : 'Risk',
    trend: locale === 'pl' ? 'Trend 7d' : '7d trend',
    sanctions: locale === 'pl' ? 'Sankcje' : 'Sanctions',
    evidence: locale === 'pl' ? 'Dowody' : 'Evidence',
    online: locale === 'pl' ? 'Dane online' : 'Online data',
    demo: locale === 'pl' ? 'Dane demo' : 'Demo data',
  };

  return (
    <div>
      <div className="flex items-center justify-between gap-4 mb-4 bg-[var(--surface)] border border-[var(--border)] px-4 py-3">
        <p className="eyebrow">{title} · {companies.length}</p>
        <hr className="hr-rule flex-1" />
      </div>

      <div className="hidden lg:block border border-[var(--border)] bg-[var(--surface)] overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead className="bg-[var(--gov-blue)] text-[var(--accent-fg)]">
            <tr>
              {[labels.entity, labels.source, labels.stock, labels.score, labels.risk, labels.trend, labels.sanctions, labels.evidence].map((label) => (
                <th key={label} className="px-4 py-3 text-left text-[11px] uppercase tracking-[0.08em] font-extrabold border-r border-[var(--accent-rule)] last:border-r-0">
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--rule)]">
            {companies.map((company) => {
              const risk = getRiskLevel(company.current_score);
              const momentumDelta = company.momentum_7d?.delta ?? 0;
              const momentumDirection = momentumTone(momentumDelta);
              const sourceIsDemo = isDemoCompany(company);
              const sanctions = sanctionsStatus(company, locale);
              const nip = nipStatus(company, locale);
              const evidence = evidenceStatus(company, locale);
              return (
                <tr key={company.id} className="hover:bg-[var(--surface-alt)] transition-colors">
                  <td className="px-4 py-3 min-w-[280px] border-r border-[var(--rule)]">
                    <Link href={`/companies/${company.id}`} className="font-extrabold text-[var(--ink)] hover:text-[var(--link)]">
                      {company.name}
                    </Link>
                    <div className="mt-1 flex items-center gap-3 text-[11px] text-[var(--ink-muted)] font-mono tnum">
                      <span>{nipLabel}: {company.nip ?? '—'}</span>
                      <span className={`px-1.5 py-0.5 border text-[9px] uppercase tracking-[0.08em] font-extrabold ${nip.className}`}>
                        {nip.label}
                      </span>
                      <span>ID: {company.id}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 border-r border-[var(--rule)]">
                    <span className={[
                      'inline-flex px-2 py-1 border text-[10px] uppercase tracking-[0.08em] font-extrabold',
                      sourceIsDemo
                        ? 'border-[var(--risk-medium-rule)] bg-[var(--risk-medium-bg)] text-[var(--risk-medium)]'
                        : 'border-[var(--border)] bg-[var(--surface-alt)] text-[var(--ink-muted)]',
                    ].join(' ')}>
                      {sourceIsDemo ? labels.demo : labels.online}
                    </span>
                  </td>
                  <td className="px-4 py-3 border-r border-[var(--rule)] font-mono tnum text-[var(--ink-2)]">
                    {company.ticker_gpw ?? '—'}
                  </td>
                  <td className="px-4 py-3 border-r border-[var(--rule)]">
                    <span className="text-2xl font-extrabold tnum" style={{ color: `var(--risk-${risk})` }}>
                      {formatScore(company.current_score)}
                    </span>
                    <span className="text-[11px] text-[var(--ink-faint)] ml-1">/100</span>
                  </td>
                  <td className="px-4 py-3 border-r border-[var(--rule)]">
                    <span className={`inline-flex px-2 py-1 border text-[10px] uppercase tracking-[0.08em] font-extrabold ${riskBadgeClass[risk]}`}>
                      {riskLabels[risk]}
                    </span>
                  </td>
                  <td className="px-4 py-3 border-r border-[var(--rule)]">
                    {company.momentum_7d ? (
                      <span className={`inline-flex px-2 py-1 border text-[12px] font-extrabold tnum ${momentumBadgeClass[momentumDirection]}`}>
                        {momentumSymbol(momentumDelta)} {formatMomentumDelta(momentumDelta)}
                      </span>
                    ) : (
                      <span className="text-[var(--ink-faint)]">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex px-2 py-1 border text-[10px] uppercase tracking-[0.08em] font-extrabold ${sanctions.className}`}>
                      {sanctions.label}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex px-2 py-1 border text-[10px] uppercase tracking-[0.08em] font-extrabold ${evidence.className}`}>
                      {evidence.label}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 lg:hidden">
        {companies.map((company, i) => (
          <CompanyCard
            key={company.id}
            company={company}
            animationDelay={Math.min((animationOffset + i) * 35, 280)}
          />
        ))}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { t, locale, formatTime, formatDate } = useI18n();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sort, setSort] = useState<SortMode>('risk_desc');
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchCompanies = useCallback(async () => {
    try {
      const data = await getCompanies();
      setCompanies(data);
      setLastUpdated(new Date());
      setError(null);
    } catch (e) {
      setError(t.dashboard.errorBody);
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [t.dashboard.errorBody]);

  useEffect(() => {
    fetchCompanies();
    const interval = setInterval(fetchCompanies, 60_000);
    return () => clearInterval(interval);
  }, [fetchCompanies]);

  const sorted = [...companies].sort((a, b) => {
    if (sort === 'risk_desc') return a.current_score - b.current_score;
    if (sort === 'risk_asc') return b.current_score - a.current_score;
    if (sort === 'trend_desc') return (a.momentum_7d?.delta ?? 0) - (b.momentum_7d?.delta ?? 0);
    return a.name.localeCompare(b.name, locale === 'pl' ? 'pl' : 'en');
  });
  const onlineCompanies = sorted.filter((company) => !isDemoCompany(company));
  const demoCompanies = sorted.filter(isDemoCompany);

  const highRisk = companies.filter((c) => getRiskLevel(c.current_score) === 'high').length;
  const medRisk = companies.filter((c) => getRiskLevel(c.current_score) === 'medium').length;
  const lowRisk = companies.filter((c) => getRiskLevel(c.current_score) === 'low').length;

  const sortOptions: ReadonlyArray<readonly [SortMode, string]> = [
    ['risk_desc', t.dashboard.sortRiskDesc],
    ['risk_asc', t.dashboard.sortRiskAsc],
    ['trend_desc', locale === 'pl' ? 'Trend ↓' : 'Trend ↓'],
    ['name', t.dashboard.sortName],
  ];

  const stats = [
    { key: 'high', label: t.dashboard.statHigh, value: highRisk, color: 'var(--risk-high)' },
    { key: 'medium', label: t.dashboard.statMedium, value: medRisk, color: 'var(--risk-medium)' },
    { key: 'low', label: t.dashboard.statLow, value: lowRisk, color: 'var(--risk-low)' },
  ];
  const riskLabels = {
    high: t.card.riskHigh,
    medium: t.card.riskMedium,
    low: t.card.riskLow,
  } as const;
  const demoScenarios = pickDemoScenarios(companies, locale);

  const today = new Date();

  return (
    <div className="min-h-screen flex flex-col">
      <Header
        rightSlot={
          <span className="tnum">
            {locale === 'pl' ? 'Dane na' : 'Data as of'}{' '}
            {formatDate(today, { day: '2-digit', month: '2-digit', year: 'numeric' })}
            {lastUpdated && (
              <>
                {' · '}
                {t.dashboard.lastUpdated} {formatTime(lastUpdated)}
              </>
            )}
          </span>
        }
      />

      <LocaleFade>
        <main className="flex-1">
          <section className="bg-[var(--surface)] border-b border-[var(--border)]">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10">
              <div className="gov-panel">
                <div className="gov-section-header">
                  <span>{locale === 'pl' ? 'Centralny rejestr oceny ryzyka' : 'Central risk assessment registry'}</span>
                  <span className="hidden sm:inline tnum">FANUM-AML-01</span>
                </div>
                <div className="p-5 sm:p-7 grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
                  <div>
                    <p className="eyebrow mb-3">
                      {locale === 'pl' ? 'Rejestr publiczny · Dane online i demonstracyjne' : 'Public registry · Online and demo data'}
                    </p>
                    <h1 className="text-3xl sm:text-[42px] font-extrabold tracking-tight text-[var(--ink)] leading-[1.05]">
                      {t.dashboard.title}{' '}
                      <span style={{ color: 'var(--crimson)' }}>{t.dashboard.titleAccent}</span>
                    </h1>
                    <p className="mt-4 text-[var(--ink-2)] text-base leading-7 max-w-3xl">
                      {t.dashboard.subtitle}
                    </p>
                  </div>
                  <div className="border border-[var(--border)] bg-[var(--surface-alt)]">
                    <div className="gov-meta-row">
                      <div className="gov-meta-label">{locale === 'pl' ? 'Status' : 'Status'}</div>
                      <div className="gov-meta-value font-semibold">{locale === 'pl' ? 'Aktywny monitoring' : 'Active monitoring'}</div>
                    </div>
                    <div className="gov-meta-row">
                      <div className="gov-meta-label">{locale === 'pl' ? 'Zakres' : 'Scope'}</div>
                      <div className="gov-meta-value">AML / media / sanctions / GPW</div>
                    </div>
                    <div className="gov-meta-row">
                      <div className="gov-meta-label">{locale === 'pl' ? 'Aktualizacja' : 'Updated'}</div>
                      <div className="gov-meta-value tnum">{lastUpdated ? formatTime(lastUpdated) : '—'}</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section className="bg-[var(--paper-2)] border-b border-[var(--border)]">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-7">
              <div className="mb-3 flex items-center gap-3">
                <span className="w-2 h-8 bg-[var(--gov-blue)]" aria-hidden="true" />
                <div>
                  <p className="text-[13px] font-extrabold uppercase tracking-[0.08em] text-[var(--ink)]">
                    {locale === 'pl' ? 'Wyszukiwarka rejestru' : 'Registry search'}
                  </p>
                  <p className="text-[12px] text-[var(--ink-muted)]">
                    {locale === 'pl' ? 'Nazwa podmiotu, NIP lub alias' : 'Entity name, tax ID or alias'}
                  </p>
                </div>
              </div>
              <SearchBar />
            </div>
          </section>

          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-10">
            {!loading && !error && (
              <section>
                  <h2 className="section-title">
                    {locale === 'pl' ? 'Podsumowanie ryzyka' : 'Risk summary'}
                  </h2>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-0 border border-[var(--border)] bg-[var(--surface)]">
                  {stats.map((s, idx) => (
                    <div
                      key={s.key}
                      className={[
                        'p-5 sm:p-6',
                        idx !== stats.length - 1 ? 'sm:border-r border-[var(--border)]' : '',
                        idx !== stats.length - 1 ? 'border-b sm:border-b-0' : '',
                      ].join(' ')}
                    >
                      <div className="flex items-center gap-2 mb-2">
                        <span
                          className="inline-block w-2 h-2"
                          style={{ background: s.color }}
                          aria-hidden="true"
                        />
                        <p className="eyebrow">{s.label}</p>
                      </div>
                      <p
                        className="text-4xl font-semibold tnum tracking-tight leading-none"
                        style={{ color: s.color }}
                      >
                        {s.value}
                      </p>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {!loading && !error && demoScenarios.length > 0 && (
              <section>
                <h2 className="section-title">
                  {locale === 'pl' ? 'Scenariusze demo dla jury' : 'Guided jury demo scenarios'}
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-0 border border-[var(--border)] bg-[var(--surface)]">
                  {demoScenarios.map((scenario, index) => {
                    const company = scenario.company;
                    if (!company) return null;
                    const risk = getRiskLevel(company.current_score);
                    return (
                      <Link
                        key={scenario.key}
                        href={`/companies/${company.id}`}
                        className={`no-underline p-5 hover:bg-[var(--surface-alt)] transition-colors ${
                          index !== demoScenarios.length - 1 ? 'border-b md:border-b-0 md:border-r border-[var(--border)]' : ''
                        }`}
                      >
                        <div className="flex items-center justify-between gap-3 mb-3">
                          <span className={`px-2 py-1 border text-[10px] uppercase tracking-[0.08em] font-extrabold ${riskBadgeClass[scenario.tone]}`}>
                            {scenario.title}
                          </span>
                          <span className="font-mono tnum text-[12px] text-[var(--ink-muted)]">#{company.id}</span>
                        </div>
                        <p className="font-extrabold text-[var(--ink)] leading-snug">{company.name}</p>
                        <p className="text-sm text-[var(--ink-2)] mt-2 leading-relaxed">{scenario.description}</p>
                        <div className="mt-4 flex items-center justify-between text-[12px]">
                          <span className="font-extrabold tnum" style={{ color: `var(--risk-${risk})` }}>
                            {formatScore(company.current_score)}/100
                          </span>
                          <span className="text-[var(--ink-muted)]">
                            {locale === 'pl' ? 'Otwórz kartę' : 'Open record'}
                          </span>
                        </div>
                      </Link>
                    );
                  })}
                </div>
              </section>
            )}

            <section>
              <div className="flex items-end justify-between gap-4 flex-wrap mb-5">
                <div>
                  <h2 className="text-[15px] font-extrabold uppercase tracking-[0.1em] text-[var(--ink)]">
                    {locale === 'pl' ? 'Wykaz podmiotów' : 'Entity list'}
                  </h2>
                  <p className="text-[12px] text-[var(--ink-muted)] mt-1">
                    {loading ? t.dashboard.loading : t.dashboard.companiesCount(companies.length)}
                  </p>
                </div>
                <div className="flex items-center gap-2 text-[11px]">
                  <span className="eyebrow !text-[10px]">{t.dashboard.sortBy}</span>
                  <div className="inline-flex border border-[var(--border-strong)] bg-[var(--surface)]">
                    {sortOptions.map(([val, label], i) => (
                      <button
                        key={val}
                        onClick={() => setSort(val)}
                        className={[
                          'px-3 h-8 text-[11px] font-semibold uppercase tracking-[0.06em] transition-colors',
                          i !== 0 ? 'border-l border-[var(--ink)]' : '',
                          sort === val
                            ? 'bg-[var(--gov-blue)] text-[var(--accent-fg)]'
                            : 'bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--paper-2)]',
                        ].join(' ')}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
              <hr className="hr-strong mb-6" />

              {loading && (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {Array.from({ length: 6 }).map((_, i) => (
                    <div key={i} className="h-44 skeleton" />
                  ))}
                </div>
              )}

              {error && (
                <div
                  className="border border-[var(--risk-high-rule)] p-6 flex items-start gap-4"
                  style={{ background: 'var(--risk-high-bg)' }}
                >
                  <div className="flex-1">
                    <p className="font-semibold text-[12px] uppercase tracking-[0.12em]" style={{ color: 'var(--crimson-2)' }}>
                      {t.dashboard.errorTitle}
                    </p>
                    <p className="text-sm text-[var(--ink-2)] mt-1">{error}</p>
                  </div>
                  <button onClick={fetchCompanies} className="doc-btn doc-btn--danger">
                    {t.dashboard.errorRetry}
                  </button>
                </div>
              )}

              {!loading && !error && sorted.length === 0 && (
                <div
                  className="border border-[var(--border)] bg-[var(--surface)] p-10 text-center"
                  style={{ borderRadius: '2px' }}
                >
                  <p className="text-[var(--ink)] font-semibold">{t.dashboard.emptyTitle}</p>
                  <p className="text-sm text-[var(--ink-muted)] mt-1">{t.dashboard.emptySubtitle}</p>
                </div>
              )}

              {!loading && !error && sorted.length > 0 && (
                <div className="space-y-10">
                  {onlineCompanies.length > 0 && (
                    <RegistrySection
                      title={locale === 'pl' ? 'Dane internetowe' : 'Online data'}
                      companies={onlineCompanies}
                      locale={locale}
                      nipLabel={t.card.nip}
                      riskLabels={riskLabels}
                    />
                  )}

                  {demoCompanies.length > 0 && (
                    <RegistrySection
                      title={locale === 'pl' ? 'Dane demo' : 'Demo data'}
                      companies={demoCompanies}
                      locale={locale}
                      nipLabel={t.card.nip}
                      riskLabels={riskLabels}
                      animationOffset={onlineCompanies.length}
                    />
                  )}
                </div>
              )}
            </section>
          </div>
        </main>
      </LocaleFade>

      <footer className="border-t border-[var(--border)] bg-[var(--surface)] mt-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-[11px] text-[var(--ink-muted)]">
          <p className="uppercase tracking-[0.1em]">
            © {today.getFullYear()} FanumFraud
          </p>
          <p>
            {locale === 'pl'
              ? 'Monitor reputacji podmiotów gospodarczych'
              : 'Corporate reputation monitor'}
          </p>
        </div>
      </footer>
    </div>
  );
}
