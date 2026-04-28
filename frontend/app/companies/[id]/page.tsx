'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  getCompanyDetail,
  getCompanyScore,
  getCompanyArticles,
  type Company,
  type CompanyScoreResponse,
  type Article,
  type ScorePoint,
} from '@/lib/api';
import ScoreChart from '@/components/ScoreChart';
import AlertBanner from '@/components/AlertBanner';
import Header from '@/components/Header';
import LocaleFade from '@/components/LocaleFade';
import Link from 'next/link';
import { formatMomentumDelta, formatScore, getRiskLevel, momentumSymbol, momentumTone, scoreDrop } from '@/lib/risk';
import { CATEGORY_ORDER, normalizeCategory, type CanonicalCategory } from '@/lib/categories';
import { useI18n } from '@/lib/i18n/I18nProvider';

const riskCssVar = {
  high: 'var(--risk-high)',
  medium: 'var(--risk-medium)',
  low: 'var(--risk-low)',
} as const;

const riskBgVar = {
  high: 'var(--risk-high-bg)',
  medium: 'var(--risk-medium-bg)',
  low: 'var(--risk-low-bg)',
} as const;

const riskRuleVar = {
  high: 'var(--risk-high-rule)',
  medium: 'var(--risk-medium-rule)',
  low: 'var(--risk-low-rule)',
} as const;

const momentumToneStyles = {
  bad: {
    color: 'var(--risk-high)',
    background: 'var(--risk-high-bg)',
    border: 'var(--risk-high-rule)',
  },
  neutral: {
    color: 'var(--ink-muted)',
    background: 'var(--surface-alt)',
    border: 'var(--border)',
  },
  good: {
    color: 'var(--risk-low)',
    background: 'var(--risk-low-bg)',
    border: 'var(--risk-low-rule)',
  },
} as const;

function momentumLabel(label: string | undefined, locale: string): string {
  const pl = {
    rapid_deterioration: 'Gwałtowne pogorszenie',
    declining: 'Pogarsza się',
    stable: 'Stabilnie',
    recovering: 'Odbudowa',
    strong_recovery: 'Silna odbudowa',
  } as const;
  const en = {
    rapid_deterioration: 'Rapid deterioration',
    declining: 'Declining',
    stable: 'Stable',
    recovering: 'Recovering',
    strong_recovery: 'Strong recovery',
  } as const;
  const dictionary = locale === 'pl' ? pl : en;
  return dictionary[label as keyof typeof dictionary] ?? dictionary.stable;
}

function checkScoreDelta(history: ScorePoint[] | undefined): { show: boolean; delta?: number } {
  if (!history || history.length < 2) return { show: false };
  const sorted = [...history].sort(
    (a, b) => new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime(),
  );
  const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
  const oldestInRange = sorted.find((p) => new Date(p.recorded_at) >= sevenDaysAgo);
  const newest = sorted[sorted.length - 1];
  if (!oldestInRange || !newest) return { show: false };
  const drop = scoreDrop(oldestInRange.score, newest.score);
  return { show: drop > 20, delta: drop };
}

export default function CompanyDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { t, formatDate, locale } = useI18n();
  const id = params.id as string;

  const [company, setCompany] = useState<Company | null>(null);
  const [scoreData, setScoreData] = useState<CompanyScoreResponse | null>(null);
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);
        const [companyData, scoreResp, articlesData] = await Promise.all([
          getCompanyDetail(Number(id)),
          getCompanyScore(Number(id)),
          getCompanyArticles(Number(id), { days: 180, limit: 20 }),
        ]);
        setCompany(companyData);
        setScoreData(scoreResp);
        setArticles(articlesData);
      } catch (e) {
        setError(t.detail.errorBody);
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [id, t.detail.errorBody]);

  const backButton = (
    <button
      onClick={() => router.back()}
      className="inline-flex items-center gap-1.5 text-[12px] uppercase tracking-[0.08em] font-semibold text-[var(--ink)] hover:text-[var(--link)] transition-colors"
    >
      <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
      </svg>
      {t.nav.back}
    </button>
  );

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col">
        <Header leftSlot={backButton} />
        <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-10 space-y-5">
          <div className="h-12 skeleton" />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="h-44 skeleton" />
            <div className="h-44 skeleton" />
          </div>
          <div className="h-72 skeleton" />
        </main>
      </div>
    );
  }

  if (error || !company || !scoreData) {
    return (
      <div className="min-h-screen flex flex-col">
        <Header leftSlot={backButton} />
        <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-10">
          <div
            className="border border-[var(--risk-high-rule)] p-6"
            style={{ background: 'var(--risk-high-bg)' }}
          >
            <p className="font-semibold text-[12px] uppercase tracking-[0.12em]" style={{ color: 'var(--crimson-2)' }}>
              {t.detail.errorTitle}
            </p>
            <p className="text-sm text-[var(--ink-2)] mt-1">{error ?? t.detail.errorBody}</p>
            <Link href="/" className="doc-btn doc-btn--primary mt-4 no-underline">
              {t.detail.errorBack}
            </Link>
          </div>
        </main>
      </div>
    );
  }

  const risk = getRiskLevel(company.current_score);
  const riskColor = riskCssVar[risk];
  const riskBg = riskBgVar[risk];
  const riskRule = riskRuleVar[risk];
  const riskLabels = {
    high: t.card.riskHigh,
    medium: t.card.riskMedium,
    low: t.card.riskLow,
  } as const;
  const exposureLabels = {
    high: t.detail.exposureHigh,
    medium: t.detail.exposureMedium,
    low: t.detail.exposureLow,
  } as const;

  const categoryCounts = scoreData.history.reduce((acc, point) => {
    const category = normalizeCategory(point.category);
    acc[category] = (acc[category] ?? 0) + 1;
    return acc;
  }, {} as Record<CanonicalCategory, number>);

  const categoryCards = CATEGORY_ORDER
    .map((category) => ({
      id: category,
      label: t.categories[category],
      count: categoryCounts[category] ?? 0,
    }))
    .filter((category) => category.count > 0);

  const formattedDate = formatDate(company.created_at);
  const max = scoreData.history.length > 0 ? Math.max(...scoreData.history.map((p) => p.score)) : null;
  const min = scoreData.history.length > 0 ? Math.min(...scoreData.history.map((p) => p.score)) : null;
  const momentum7d = scoreData.momentum_7d ?? company.momentum_7d;
  const momentum30d = scoreData.momentum_30d ?? company.momentum_30d;
  const dominantCategory = categoryCards[0]?.label ?? (locale === 'pl' ? 'Brak dominującej kategorii' : 'No dominant category');
  const latestArticle = articles[0];
  const fallbackAlert = checkScoreDelta(scoreData.history);
  const backendDrop = momentum7d && momentum7d.delta <= -20 ? Math.abs(momentum7d.delta) : undefined;
  const showAlert = backendDrop != null || fallbackAlert.show;
  const scoreDelta = backendDrop ?? fallbackAlert.delta;

  return (
    <div className="min-h-screen flex flex-col">
      <Header leftSlot={backButton} />

      <LocaleFade>
        <main className="flex-1">
          <section className="bg-[var(--surface)] border-b border-[var(--border)]">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10">
              <div className="gov-panel">
                <div className="gov-section-header">
                  <span>{locale === 'pl' ? 'Karta podmiotu' : 'Entity record'} · #{company.id}</span>
                  <span>{riskLabels[risk]}</span>
                </div>
                <div className="p-5 sm:p-7">
                  <div className="flex items-start justify-between gap-5 flex-wrap">
                    <div className="flex items-start gap-4 min-w-0">
                      <span
                        className="mt-1 w-3 h-14 shrink-0"
                        style={{ background: riskColor }}
                        aria-hidden="true"
                      />
                      <div className="min-w-0">
                        <p className="eyebrow mb-2">
                          {locale === 'pl' ? 'Profil w rejestrze ryzyka' : 'Risk registry profile'}
                        </p>
                        <h1 className="text-3xl sm:text-[40px] font-extrabold tracking-tight text-[var(--ink)] leading-[1.05]">
                          {company.name}
                        </h1>
                      </div>
                    </div>
                    <button
                      onClick={() => {
                        const link = document.createElement('a');
                        link.href = `/api/companies/${company.id}/export`;
                        link.download = `risk_report_${company.id}.pdf`;
                        link.click();
                      }}
                      className="doc-btn doc-btn--primary"
                    >
                      PDF {locale === 'pl' ? 'Eksportuj' : 'Export'}
                    </button>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 border border-[var(--border)] mt-6">
                    <div className="gov-meta-row sm:block">
                      <div className="gov-meta-label">{locale === 'pl' ? 'Status ryzyka' : 'Risk status'}</div>
                      <div className="gov-meta-value">
                        <span className="px-2 py-1 border font-extrabold uppercase tracking-[0.1em] text-[10px]" style={{ background: riskBg, borderColor: riskRule, color: riskColor }}>
                          {riskLabels[risk]}
                        </span>
                      </div>
                    </div>
                    <div className="gov-meta-row sm:block">
                      <div className="gov-meta-label">{t.card.nip}</div>
                      <div className="gov-meta-value font-mono tnum">{company.nip ?? '—'}</div>
                    </div>
                    <div className="gov-meta-row sm:block">
                      <div className="gov-meta-label">GPW</div>
                      <div className="gov-meta-value font-mono tnum">{company.ticker_gpw ?? '—'}</div>
                    </div>
                    <div className="gov-meta-row sm:block">
                      <div className="gov-meta-label">{t.detail.addedOn}</div>
                      <div className="gov-meta-value tnum">{formattedDate}</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-12">
            {showAlert && <AlertBanner show={true} scoreDelta={scoreDelta} />}

            {company.sanctions?.status === 'unavailable' && (
              <section
                className="p-6 border"
                style={{
                  borderColor: 'var(--risk-medium-rule)',
                  background: 'var(--risk-medium-bg)',
                }}
              >
                <div className="flex items-start gap-3">
                  <span className="text-2xl" aria-hidden="true">!</span>
                  <div className="flex-1">
                    <h3
                      className="font-extrabold text-lg mb-2 uppercase tracking-[0.04em]"
                      style={{ color: 'var(--risk-medium)' }}
                    >
                      {locale === 'pl' ? 'NIE SPRAWDZONO LIST SANKCYJNYCH' : 'SANCTIONS CHECK NOT COMPLETED'}
                    </h3>
                    <p className="text-sm text-[var(--ink-2)] mb-2">
                      {locale === 'pl'
                        ? 'Brak wpisu nie został potwierdzony, ponieważ zewnętrzne źródło sankcyjne jest niedostępne lub nie skonfigurowano klucza API.'
                        : 'A clear result has not been confirmed because the external sanctions source is unavailable or the API key is not configured.'}
                    </p>
                    <p className="text-[12px] text-[var(--ink-muted)] font-mono tnum">
                      source={company.sanctions.source}{company.sanctions.reason ? ` · ${company.sanctions.reason}` : ''}
                    </p>
                  </div>
                </div>
              </section>
            )}

            {company.sanctions?.is_sanctioned && (
              <section
                className="p-6 border"
                style={{
                  borderColor: 'var(--risk-high-rule)',
                  background: 'var(--risk-high-bg)',
                }}
              >
                <div className="flex items-start gap-3">
                  <span className="text-2xl">🚩</span>
                  <div className="flex-1">
                    <h3
                      className="font-semibold text-lg mb-2"
                      style={{ color: 'var(--risk-high)' }}
                    >
                      {locale === 'pl' ? 'FIRMA NA LIŚCIE SANKCJI' : 'ON SANCTIONS LIST'}
                    </h3>
                    <p className="text-sm text-[var(--ink-2)] mb-3">
                      {locale === 'pl'
                        ? `Ta firma występuje na ${company.sanctions.lists.length} liście(ach) sankcji międzynarodowych.`
                        : `This company appears on ${company.sanctions.lists.length} international sanctions list(s).`}
                    </p>
                    <p className="text-[12px] text-[var(--ink-muted)] font-mono tnum mb-3">
                      source={company.sanctions.source} · confidence={(company.sanctions.confidence * 100).toFixed(0)}%
                    </p>
                    <div className="space-y-2">
                      {company.sanctions.lists.map((list, idx) => (
                        <div
                          key={idx}
                            className="flex items-center justify-between text-sm p-2 bg-[var(--surface)] border border-[var(--risk-high-rule)]"
                        >
                          <div>
                            <span className="font-semibold">{list.name}</span>
                            <span className="text-[var(--ink-muted)] ml-2">
                              {list.country}
                            </span>
                          </div>
                          <span className="text-xs font-mono text-[var(--ink-2)]">
                            {(list.match_score * 100).toFixed(0)}%
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </section>
            )}

            <section>
              <div className="gov-panel grid grid-cols-1 lg:grid-cols-5 gap-0">
                <div className="p-6 lg:col-span-2 lg:border-r border-b lg:border-b-0 border-[var(--border)]">
                  <p className="eyebrow mb-3">{t.detail.currentScore}</p>
                  <p
                    className="text-[64px] font-semibold tnum leading-none tracking-tight"
                    style={{ color: riskColor }}
                  >
                    {formatScore(company.current_score)}
                    <span className="text-2xl font-medium text-[var(--ink-faint)] ml-1">
                      {t.card.scoreOutOf}
                    </span>
                  </p>
                  <div className="h-1.5 w-full bg-[var(--paper-2)] border border-[var(--rule)] mt-4">
                    <div
                      className="h-full transition-[width] duration-700 ease-out"
                      style={{ width: `${Math.max(0, Math.min(100, company.current_score))}%`, background: riskColor }}
                    />
                  </div>
                  <p className="text-[12px] text-[var(--ink-2)] mt-3">
                    <span className="font-semibold uppercase tracking-[0.08em] text-[10px] mr-1.5" style={{ color: riskColor }}>
                      ●
                    </span>
                    {exposureLabels[risk]}
                  </p>
                </div>

                <div className={`lg:col-span-3 grid ${company.stock_price ? 'grid-cols-2 sm:grid-cols-4' : 'grid-cols-3'}`}>
                  {[
                    { label: t.detail.statsMax, value: max != null ? max.toFixed(0) : '—' },
                    { label: t.detail.statsMin, value: min != null ? min.toFixed(0) : '—' },
                    { label: t.detail.statsCount, value: scoreData.history.length.toString() },
                    ...(company.stock_price ? [{ 
                      label: `Akcje (${company.ticker_gpw})`, 
                      value: `${company.stock_price.price.toFixed(2)} PLN`,
                      subtext: `${company.stock_price.change_percent > 0 ? '+' : ''}${company.stock_price.change_percent.toFixed(2)}%`,
                      subtextColor: company.stock_price.change_percent >= 0 ? 'var(--risk-low)' : 'var(--risk-high)'
                    }] : [])
                  ].map((cell, i, arr) => (
                    <div
                      key={cell.label}
                      className={['p-6', i !== arr.length - 1 ? 'border-r border-[var(--border)]' : ''].join(' ')}
                    >
                      <p className="eyebrow mb-2">{cell.label}</p>
                      <p className={`text-2xl lg:text-3xl font-semibold tnum text-[var(--ink)] leading-none ${cell.value.includes('PLN') ? 'text-xl lg:text-2xl' : ''}`}>
                        {cell.value}
                      </p>
                      {cell.subtext && (
                        <p className="text-[14px] font-semibold tnum mt-2" style={{ color: cell.subtextColor }}>
                          {cell.subtext}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </section>

            <section>
              <h2 className="section-title">
                {locale === 'pl' ? 'Trend reputacji' : 'Reputation trend'}
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-0 border border-[var(--border)] bg-[var(--surface)]">
                {[momentum7d, momentum30d].map((momentum, index) => {
                  const delta = momentum?.delta ?? 0;
                  const toneStyle = momentumToneStyles[momentumTone(delta)];
                  const windowLabel = index === 0 ? '7d' : '30d';
                  return (
                    <div
                      key={windowLabel}
                      className={[
                        'p-5 sm:p-6',
                        index === 0 ? 'border-b md:border-b-0 md:border-r border-[var(--border)]' : '',
                      ].join(' ')}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="eyebrow mb-2">
                            {locale === 'pl' ? `Momentum ${windowLabel}` : `${windowLabel} momentum`}
                          </p>
                          <p className="text-[34px] font-semibold tnum leading-none" style={{ color: toneStyle.color }}>
                            {momentum ? `${momentumSymbol(delta)} ${formatMomentumDelta(delta)}` : '—'}
                          </p>
                        </div>
                        <span
                          className="px-2 py-1 border text-[10px] uppercase tracking-[0.1em] font-semibold"
                          style={{ color: toneStyle.color, background: toneStyle.background, borderColor: toneStyle.border }}
                        >
                          {momentumLabel(momentum?.label, locale)}
                        </span>
                      </div>
                      <p className="text-sm text-[var(--ink-2)] mt-4 leading-relaxed">
                        {momentum
                          ? locale === 'pl'
                            ? `Zmiana z ${momentum.past_score.toFixed(0)} do ${momentum.current_score.toFixed(0)} punktów w oknie ${momentum.window_days} dni.`
                            : `Moved from ${momentum.past_score.toFixed(0)} to ${momentum.current_score.toFixed(0)} points over ${momentum.window_days} days.`
                          : locale === 'pl'
                            ? 'Brak wystarczającej historii do obliczenia trendu.'
                            : 'Not enough history to calculate trend.'}
                      </p>
                    </div>
                  );
                })}
              </div>
            </section>

            <section>
              <h2 className="section-title">
                {locale === 'pl' ? 'Dlaczego taki scoring?' : 'Why this score?'}
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-0 border border-[var(--border)] bg-[var(--surface)]">
                {[
                  {
                    label: locale === 'pl' ? 'Dominująca kategoria' : 'Dominant category',
                    value: dominantCategory,
                    help: locale === 'pl'
                      ? 'Najczęściej występujący typ ryzyka w historii scoringu.'
                      : 'Most frequent risk type in the score history.',
                  },
                  {
                    label: locale === 'pl' ? 'Ostatni sygnał' : 'Latest signal',
                    value: latestArticle?.source ?? (locale === 'pl' ? 'Brak publikacji' : 'No coverage'),
                    help: latestArticle?.published_at
                      ? formatDate(latestArticle.published_at, { day: '2-digit', month: 'short', year: 'numeric' })
                      : locale === 'pl' ? 'Nie wykryto powiązanych artykułów.' : 'No related articles detected.',
                  },
                  {
                    label: locale === 'pl' ? 'Wolumen dowodów' : 'Evidence volume',
                    value: scoreData.history.length.toString(),
                    help: locale === 'pl'
                      ? 'Liczba punktów historii wpływających na profil reputacyjny.'
                      : 'Number of history points shaping the reputation profile.',
                  },
                ].map((item, index) => (
                  <div
                    key={item.label}
                    className={[
                      'p-5 sm:p-6',
                      index !== 2 ? 'border-b md:border-b-0 md:border-r border-[var(--border)]' : '',
                    ].join(' ')}
                  >
                    <p className="eyebrow mb-2">{item.label}</p>
                    <p className="text-xl font-semibold text-[var(--ink)] leading-tight">{item.value}</p>
                    <p className="text-sm text-[var(--ink-muted)] mt-3 leading-relaxed">{item.help}</p>
                  </div>
                ))}
              </div>
            </section>

            <section>
              <h2 className="section-title">{t.detail.chartTitle}</h2>
              <ScoreChart history={scoreData.history} />
            </section>

            {scoreData.history.length > 0 && (
              <section>
                <h2 className="section-title">{t.detail.categoriesTitle}</h2>
                {categoryCards.length > 0 ? (
                  <div className="border border-[var(--border)] bg-[var(--surface)] divide-y divide-[var(--rule)]">
                    {categoryCards.map((category) => (
                      <div
                        key={category.id}
                        className="flex items-center justify-between gap-4 px-5 py-3.5 hover:bg-[var(--surface-alt)] transition-colors"
                      >
                        <p className="text-sm text-[var(--ink)]">{category.label}</p>
                        <p className="text-sm font-semibold tnum text-[var(--ink)]">
                          {category.count}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-[var(--ink-muted)] py-2">
                    {t.detail.categoriesEmpty}
                  </p>
                )}
              </section>
            )}

            <section>
              <h2 className="section-title">{t.detail.articlesTitle}</h2>
              {articles.length === 0 ? (
                <p className="text-sm text-[var(--ink-muted)] py-2">
                  {t.detail.articlesEmpty}
                </p>
              ) : (
                <ol className="border border-[var(--border)] bg-[var(--surface)] divide-y divide-[var(--rule)]">
                  {articles.slice(0, 5).map((article, i) => (
                    <li key={article.id} className="px-5 py-4 flex items-start gap-4 hover:bg-[var(--surface-alt)] transition-colors">
                      <span className="eyebrow mt-1 tnum w-6 shrink-0">
                        {String(i + 1).padStart(2, '0')}
                      </span>
                      <div className="flex-1 min-w-0">
                        <Link
                          href={`/articles/${article.id}`}
                          className="font-medium text-[var(--ink)] hover:text-[var(--link)] leading-snug block"
                          style={{ textDecorationColor: 'var(--rule)' }}
                        >
                          {article.title || (locale === 'pl' ? 'Artykul bez tytulu' : 'Untitled article')}
                        </Link>
                        <div className="flex items-center gap-3 mt-1 text-[11px] text-[var(--ink-muted)]">
                          {article.source && (
                            <span>
                              <span className="font-semibold">{t.detail.articleSource}:</span>{' '}
                              <span className="font-mono">{article.source}</span>
                            </span>
                          )}
                          {article.published_at && (
                            <span className="tnum">
                              {formatDate(article.published_at, {
                                day: '2-digit',
                                month: 'short',
                                year: 'numeric',
                              })}
                            </span>
                          )}
                        </div>
                      </div>
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        className="w-3.5 h-3.5 text-[var(--ink-muted)] shrink-0 mt-1"
                        fill="none" viewBox="0 0 24 24" stroke="currentColor"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </li>
                  ))}
                </ol>
              )}
            </section>
          </div>
        </main>
      </LocaleFade>

      <footer className="border-t border-[var(--border)] bg-[var(--surface)] mt-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 text-[11px] text-[var(--ink-muted)] uppercase tracking-[0.1em]">
          © {new Date().getFullYear()} FanumFraud
        </div>
      </footer>
    </div>
  );
}
