'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { getCompanyDetail, getCompanyScore, getCompanyArticles, type Company, type CompanyScoreResponse, type Article, type ScorePoint } from '@/lib/api';
import ScoreChart from '@/components/ScoreChart';
import AlertBanner from '@/components/AlertBanner';
import Link from 'next/link';
import { getRiskLevel, scoreDrop } from '@/lib/risk';
import { CATEGORY_META, CATEGORY_ORDER, normalizeCategory, type CanonicalCategory } from '@/lib/categories';

export default function CompanyDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [company, setCompany] = useState<Company | null>(null);
  const [scoreData, setScoreData] = useState<CompanyScoreResponse | null>(null);
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const riskConfig = {
    high: {
      label: 'Wysokie ryzyko',
      badge: 'bg-red-500/10 text-red-400 border border-red-500/20',
      scoreColor: 'text-red-400',
    },
    medium: {
      label: 'Średnie ryzyko',
      badge: 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20',
      scoreColor: 'text-yellow-400',
    },
    low: {
      label: 'Niskie ryzyko',
      badge: 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20',
      scoreColor: 'text-emerald-400',
    },
  };

  // Check if score dropped significantly in last 7 days.
  const checkScoreDelta = (history: ScorePoint[] | undefined): { show: boolean; delta?: number } => {
    if (!history || history.length < 2) return { show: false };

    const sorted = [...history].sort((a, b) => new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime());
    const now = new Date();
    const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);

    const oldestInRange = sorted.find((p) => new Date(p.recorded_at) >= sevenDaysAgo);
    const newest = sorted[sorted.length - 1];

    if (!oldestInRange || !newest) return { show: false };

    const drop = scoreDrop(oldestInRange.score, newest.score);
    return { show: drop > 20, delta: drop };
  };

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
        setError('Nie można załadować szczegółów firmy.');
        console.error(e);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [id]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#080b12] text-white">
        <header className="border-b border-white/5 bg-[#080b12]/80 backdrop-blur-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
            <button onClick={() => router.back()} className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors">
              <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              Powrót
            </button>
          </div>
        </header>
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="space-y-6">
            <div className="h-12 bg-white/4 rounded-2xl animate-pulse" />
            <div className="h-72 bg-white/4 rounded-2xl animate-pulse" />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <div className="h-48 bg-white/4 rounded-2xl animate-pulse" />
              <div className="h-48 bg-white/4 rounded-2xl animate-pulse" />
            </div>
          </div>
        </main>
      </div>
    );
  }

  if (error || !company || !scoreData) {
    return (
      <div className="min-h-screen bg-[#080b12] text-white">
        <header className="border-b border-white/5 bg-[#080b12]/80 backdrop-blur-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
            <button onClick={() => router.back()} className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors">
              <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              Powrót
            </button>
          </div>
        </header>
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="rounded-2xl border border-red-500/30 bg-red-500/8 p-8 text-center">
            <p className="text-red-400 font-semibold mb-2">Błąd ładowania</p>
            <p className="text-gray-500 text-sm mb-4">{error || 'Nie można załadować firmy.'}</p>
            <Link href="/" className="inline-block px-4 py-2 rounded-lg bg-blue-500/15 text-blue-400 text-sm hover:bg-blue-500/25 transition-colors">
              Wróć do strony głównej
            </Link>
          </div>
        </main>
      </div>
    );
  }

  const risk = getRiskLevel(company.current_score);
  const cfg = riskConfig[risk];
  const { show: showAlert, delta: scoreDelta } = checkScoreDelta(scoreData.history);
  const categoryCounts = scoreData.history.reduce((acc, point) => {
    const category = normalizeCategory(point.category);
    acc[category] = (acc[category] ?? 0) + 1;
    return acc;
  }, {} as Record<CanonicalCategory, number>);

  const categoryCards = CATEGORY_ORDER
    .map((category) => ({
      id: category,
      label: CATEGORY_META[category].label,
      cardClass: CATEGORY_META[category].cardClass,
      count: categoryCounts[category] ?? 0,
    }))
    .filter((category) => category.count > 0);

  const formattedDate = new Date(company.created_at).toLocaleDateString('pl-PL', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  });

  return (
    <div className="min-h-screen bg-[#080b12] text-white">
      {/* Header */}
      <header className="border-b border-white/5 bg-[#080b12]/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <button
            onClick={() => router.back()}
            className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors mb-4"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Powrót
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 space-y-8">
        {/* Alert Banner */}
        {showAlert && <AlertBanner show={true} scoreDelta={scoreDelta} />}

        {/* Company Header */}
        <section className="space-y-4">
          <div>
            <h1 className="text-4xl sm:text-5xl font-black tracking-tight mb-3">{company.name}</h1>
            <div className="flex items-center gap-3 flex-wrap">
              <span className={`text-sm font-semibold px-3 py-1 rounded-full ${cfg.badge}`}>
                {cfg.label}
              </span>
              {company.nip && (
                <p className="text-sm text-gray-500 font-mono">NIP: {company.nip}</p>
              )}
              <p className="text-sm text-gray-500">Dodana: {formattedDate}</p>
            </div>
          </div>

          {/* Score Section */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            {/* Current Score */}
            <div className="rounded-2xl border border-white/10 bg-[#0f1521] p-6 flex flex-col gap-4">
              <p className="text-xs text-gray-500 uppercase tracking-widest">Aktualna ocena ryzyka</p>
              <p className={`text-6xl font-black tabular-nums ${cfg.scoreColor}`}>
                {company.current_score}
                <span className="text-2xl font-semibold text-gray-600">/100</span>
              </p>
              <div className="h-2 w-full bg-white/5 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-blue-500 to-blue-400 transition-all duration-700"
                  style={{ width: `${company.current_score}%` }}
                />
              </div>
              <div className="text-xs text-gray-600">
                {risk === 'high' ? '🔴 Ekspozycja wysoka' : risk === 'medium' ? '🟡 Ekspozycja średnia' : '🟢 Ekspozycja niska'}
              </div>
            </div>

            {/* Score Stats */}
            <div className="rounded-2xl border border-white/10 bg-[#0f1521] p-6 flex flex-col gap-4">
              <p className="text-xs text-gray-500 uppercase tracking-widest">Statystyka</p>
              <div className="space-y-3">
                {scoreData.history.length > 0 && (
                  <>
                    <div>
                      <p className="text-xs text-gray-600 mb-1">Maksymalny score</p>
                      <p className="text-2xl font-bold text-white">
                        {Math.max(...scoreData.history.map((p) => p.score)).toFixed(0)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-600 mb-1">Minimalny score</p>
                      <p className="text-2xl font-bold text-white">
                        {Math.min(...scoreData.history.map((p) => p.score)).toFixed(0)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-600 mb-1">Liczba pomiarów</p>
                      <p className="text-2xl font-bold text-white">{scoreData.history.length}</p>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        </section>

        {/* Chart */}
        <section>
          <h2 className="text-xl font-bold mb-4">Historia scoringu</h2>
          <ScoreChart history={scoreData.history} />
        </section>

        {/* Category Breakdown */}
        {scoreData.history.length > 0 && (
          <section className="space-y-4">
            <h2 className="text-xl font-bold">Kategorie ryzyka</h2>
            {categoryCards.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {categoryCards.map((category) => (
                  <div key={category.id} className={`rounded-2xl border p-4 ${category.cardClass}`}>
                    <p className="text-sm font-semibold">{category.label}</p>
                    <p className="text-2xl font-bold mt-2">{category.count}</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-2xl border border-white/8 bg-[#0f1521] p-4 text-sm text-gray-500">
                Brak przypisanych kategorii dla dostępnych pomiarów.
              </div>
            )}
          </section>
        )}

        {/* Articles */}
        {articles.length > 0 && (
          <section className="space-y-4">
            <h2 className="text-xl font-bold">Artykuły powiązane z firmą</h2>
            <div className="grid grid-cols-1 gap-3">
              {articles.slice(0, 5).map((article) => (
                <a
                  key={article.id}
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-2xl border border-white/10 bg-[#0f1521] p-5 hover:bg-[#161e2e] transition-colors flex items-start justify-between gap-4 group"
                >
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-white group-hover:text-blue-400 transition-colors line-clamp-2">
                      {article.title}
                    </p>
                    {article.source && (
                      <p className="text-xs text-gray-600 mt-2">
                        Źródło: <span className="font-mono">{article.source}</span>
                      </p>
                    )}
                    {article.published_at && (
                      <p className="text-xs text-gray-600 mt-1">
                        {new Date(article.published_at).toLocaleDateString('pl-PL')}
                      </p>
                    )}
                  </div>
                  <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5 text-gray-500 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4m-4-4l8-8m0 0H8m8 0v8" />
                  </svg>
                </a>
              ))}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
