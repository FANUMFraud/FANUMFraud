'use client';

import { useEffect, useState, useCallback } from 'react';
import { getCompanies, type Company } from '@/lib/api';
import CompanyCard from '@/components/CompanyCard';
import SearchBar from '@/components/SearchBar';
import { getRiskLevel } from '@/lib/risk';

type SortMode = 'risk_desc' | 'risk_asc' | 'name';

export default function DashboardPage() {
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
      setError('Nie można połączyć się z API. Upewnij się, że backend jest uruchomiony na localhost:8000.');
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial fetch + refresh every 60s
  useEffect(() => {
    fetchCompanies();
    const interval = setInterval(fetchCompanies, 60_000);
    return () => clearInterval(interval);
  }, []);

  const sorted = [...companies].sort((a, b) => {
    if (sort === 'risk_desc') return a.current_score - b.current_score;
    if (sort === 'risk_asc') return b.current_score - a.current_score;
    return a.name.localeCompare(b.name, 'pl');
  });

  const highRisk = companies.filter((c) => getRiskLevel(c.current_score) === 'high').length;
  const medRisk = companies.filter((c) => getRiskLevel(c.current_score) === 'medium').length;
  const lowRisk = companies.filter((c) => getRiskLevel(c.current_score) === 'low').length;

  return (
    <div className="min-h-screen bg-[#080b12] text-white">
      {/* Header */}
      <header className="border-b border-white/5 bg-[#080b12]/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-red-500/15 border border-red-500/30 flex items-center justify-center">
              <span className="text-red-400 font-black text-sm">FF</span>
            </div>
            <span className="font-bold text-xl tracking-tight">
              Fanum<span className="text-red-400">Fraud</span>
            </span>
          </div>
          {lastUpdated && (
            <p className="text-xs text-gray-600">
              Zaktualizowano: {lastUpdated.toLocaleTimeString('pl-PL')}
            </p>
          )}
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 space-y-10">
        {/* Hero */}
        <section className="text-center space-y-4">
          <h1 className="text-4xl sm:text-5xl font-black tracking-tight">
            Monitor Ryzyka{' '}
            <span className="bg-gradient-to-r from-red-400 to-orange-400 bg-clip-text text-transparent">
              AML
            </span>
          </h1>
          <p className="text-gray-500 text-lg max-w-xl mx-auto">
            Monitoruj reputację firm w czasie rzeczywistym na podstawie polskich mediów.
          </p>
        </section>

        {/* Search */}
        <section>
          <SearchBar />
        </section>

        {/* Stats */}
        {!loading && !error && (
          <section className="grid grid-cols-3 gap-4">
            {[
              { label: 'Wysokie ryzyko', value: highRisk, color: 'text-red-400', bg: 'bg-red-500/8 border-red-500/20' },
              { label: 'Średnie ryzyko', value: medRisk, color: 'text-yellow-400', bg: 'bg-yellow-500/8 border-yellow-500/20' },
              { label: 'Niskie ryzyko', value: lowRisk, color: 'text-emerald-400', bg: 'bg-emerald-500/8 border-emerald-500/20' },
            ].map((s) => (
              <div key={s.label} className={`rounded-2xl border p-5 text-center ${s.bg}`}>
                <p className={`text-3xl font-black ${s.color}`}>{s.value}</p>
                <p className="text-xs text-gray-500 mt-1 uppercase tracking-wider">{s.label}</p>
              </div>
            ))}
          </section>
        )}

        {/* Controls */}
        <section className="flex items-center justify-between gap-4 flex-wrap">
          <p className="text-gray-500 text-sm">
            {loading ? 'Ładowanie…' : `${companies.length} firm w bazie`}
          </p>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-600 mr-1">Sortuj:</span>
            {([
              ['risk_desc', '↑ Ryzyko'],
              ['risk_asc', '↓ Ryzyko'],
              ['name', 'Nazwa'],
            ] as [SortMode, string][]).map(([val, label]) => (
              <button
                key={val}
                onClick={() => setSort(val)}
                className={`px-3 py-1.5 text-xs rounded-lg transition-colors font-medium ${
                  sort === val
                    ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                    : 'bg-white/5 text-gray-400 hover:bg-white/8 border border-transparent'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </section>

        {/* States */}
        {loading && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-52 rounded-2xl bg-white/4 animate-pulse" />
            ))}
          </div>
        )}

        {error && (
          <div className="rounded-2xl border border-red-500/30 bg-red-500/8 p-6 text-center">
            <p className="text-red-400 font-semibold mb-1">Błąd połączenia</p>
            <p className="text-gray-500 text-sm">{error}</p>
            <button
              onClick={fetchCompanies}
              className="mt-4 px-4 py-2 rounded-lg bg-red-500/15 text-red-400 text-sm hover:bg-red-500/25 transition-colors"
            >
              Spróbuj ponownie
            </button>
          </div>
        )}

        {!loading && !error && sorted.length === 0 && (
          <div className="text-center py-20 text-gray-600">
            <p className="text-lg">Brak firm w bazie danych.</p>
          </div>
        )}

        {/* Grid */}
        {!loading && !error && sorted.length > 0 && (
          <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {sorted.map((company, i) => (
              <CompanyCard
                key={company.id}
                company={company}
                animationDelay={i * 60}
              />
            ))}
          </section>
        )}
      </main>
    </div>
  );
}
