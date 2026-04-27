'use client';

import { useEffect, useState, useCallback } from 'react';
import { getCompanies, type Company } from '@/lib/api';
import CompanyCard from '@/components/CompanyCard';
import SearchBar from '@/components/SearchBar';
import Header from '@/components/Header';
import LocaleFade from '@/components/LocaleFade';
import { getRiskLevel } from '@/lib/risk';
import { useI18n } from '@/lib/i18n/I18nProvider';

type SortMode = 'risk_desc' | 'risk_asc' | 'trend_desc' | 'name';

function isDemoCompany(company: Company): boolean {
  return Boolean(company.nip?.startsWith('10100000'));
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
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-14">
              <div className="max-w-3xl">
                <p className="eyebrow mb-3">
                  {locale === 'pl' ? 'Rejestr publiczny · Dane online' : 'Public registry · Live data'}
                </p>
                <h1 className="text-3xl sm:text-[40px] font-semibold tracking-tight text-[var(--ink)] leading-[1.1]">
                  {t.dashboard.title}{' '}
                  <span style={{ color: 'var(--crimson)' }}>{t.dashboard.titleAccent}</span>
                </h1>
                <p className="mt-3 text-[var(--ink-2)] text-base leading-relaxed max-w-2xl">
                  {t.dashboard.subtitle}
                </p>
              </div>
            </div>
          </section>

          <section className="bg-[var(--paper-2)] border-b border-[var(--border)]">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
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

            <section>
              <div className="flex items-end justify-between gap-4 flex-wrap mb-5">
                <div>
                  <h2 className="text-[15px] font-semibold uppercase tracking-[0.1em] text-[var(--ink)]">
                    {locale === 'pl' ? 'Wykaz podmiotów' : 'Entity list'}
                  </h2>
                  <p className="text-[12px] text-[var(--ink-muted)] mt-1">
                    {loading ? t.dashboard.loading : t.dashboard.companiesCount(companies.length)}
                  </p>
                </div>
                <div className="flex items-center gap-2 text-[11px]">
                  <span className="eyebrow !text-[10px]">{t.dashboard.sortBy}</span>
                  <div className="inline-flex border border-[var(--ink)]">
                    {sortOptions.map(([val, label], i) => (
                      <button
                        key={val}
                        onClick={() => setSort(val)}
                        className={[
                          'px-3 h-8 text-[11px] font-semibold uppercase tracking-[0.06em] transition-colors',
                          i !== 0 ? 'border-l border-[var(--ink)]' : '',
                          sort === val
                            ? 'bg-[var(--ink)] text-[var(--surface)]'
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
                    <div>
                      <div className="flex items-center justify-between gap-4 mb-4">
                        <p className="eyebrow">
                          {locale === 'pl' ? 'Dane internetowe' : 'Online data'} · {onlineCompanies.length}
                        </p>
                        <hr className="hr-rule flex-1" />
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                        {onlineCompanies.map((company, i) => (
                          <CompanyCard
                            key={company.id}
                            company={company}
                            animationDelay={Math.min(i * 35, 280)}
                          />
                        ))}
                      </div>
                    </div>
                  )}

                  {demoCompanies.length > 0 && (
                    <div>
                      <div className="flex items-center justify-between gap-4 mb-4">
                        <p className="eyebrow">
                          {locale === 'pl' ? 'Dane demo' : 'Demo data'} · {demoCompanies.length}
                        </p>
                        <hr className="hr-rule flex-1" />
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                        {demoCompanies.map((company, i) => (
                          <CompanyCard
                            key={company.id}
                            company={company}
                            animationDelay={Math.min(i * 35, 280)}
                          />
                        ))}
                      </div>
                    </div>
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
