'use client';

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { runLiveCompanySearch, searchCompanies, type Company } from '@/lib/api';
import { getRiskLevel, formatScore } from '@/lib/risk';
import { useI18n } from '@/lib/i18n/I18nProvider';

const riskTextClass = (score: number) => {
  const r = getRiskLevel(score);
  if (r === 'high') return 'text-[var(--risk-high)]';
  if (r === 'medium') return 'text-[var(--risk-medium)]';
  return 'text-[var(--risk-low)]';
};

type LiveStatus = {
  kind: 'success' | 'error';
  text: string;
};

export default function SearchBar() {
  const { t } = useI18n();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Company[]>([]);
  const [loading, setLoading] = useState(false);
  const [liveLoading, setLiveLoading] = useState(false);
  const [liveStatus, setLiveStatus] = useState<LiveStatus | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const cleanQuery = query.trim();

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  useEffect(() => {
    if (cleanQuery.length < 2) {
      setResults([]);
      setIsOpen(false);
      return;
    }
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const data = await searchCompanies(cleanQuery);
        setResults(data);
        setIsOpen(true);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 280);
    return () => clearTimeout(timer);
  }, [cleanQuery]);

  const handleLiveSearch = async () => {
    if (cleanQuery.length < 2 || liveLoading) return;

    setLiveLoading(true);
    setLiveStatus(null);
    setIsOpen(false);
    try {
      const data = await runLiveCompanySearch(cleanQuery);
      setResults([data.company]);
      setIsOpen(true);
      setLiveStatus({
        kind: 'success',
        text: t.search.liveSuccess(data.articles_found, data.articles_scored),
      });
    } catch {
      setLiveStatus({ kind: 'error', text: t.search.liveError });
    } finally {
      setLiveLoading(false);
    }
  };

  return (
    <div ref={containerRef} className="relative w-full z-40">
      <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
        <div className="relative flex items-center">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="absolute left-4 w-[18px] h-[18px] text-[var(--ink-muted)] pointer-events-none"
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>

          <input
            type="text"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setLiveStatus(null); }}
            placeholder={t.search.placeholder}
            aria-label={t.search.placeholder}
            className="doc-input pl-12 pr-16"
          />

          {loading && !liveLoading && (
            <div className="absolute right-4">
              <div className="w-3.5 h-3.5 border-2 border-[var(--border)] border-t-[var(--ink)] rounded-full animate-spin" />
            </div>
          )}

          {!loading && cleanQuery.length > 0 && cleanQuery.length < 2 && (
            <span className="absolute right-4 text-[10px] uppercase tracking-[0.12em] font-extrabold text-[var(--ink-muted)] pointer-events-none">
              {t.search.hint}
            </span>
          )}
        </div>

        <button
          type="button"
          onClick={handleLiveSearch}
          disabled={cleanQuery.length < 2 || liveLoading}
          className="doc-btn doc-btn--primary h-12 px-4 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {liveLoading ? t.search.liveLoading : t.search.liveAction}
        </button>
      </div>

      {liveStatus && (
        <p
          aria-live="polite"
          className={`mt-2 text-xs font-semibold ${
            liveStatus.kind === 'success' ? 'text-[var(--risk-low)]' : 'text-[var(--risk-high)]'
          }`}
        >
          {liveStatus.text}
        </p>
      )}

      {isOpen && (
        <div
          className="absolute top-full mt-2 w-full bg-[var(--surface)] border-2 border-[var(--border-strong)] shadow-[0_8px_0_rgba(17,24,39,0.08)]"
          style={{ borderRadius: 0 }}
        >
          {results.length > 0 ? (
            results.map((company, i) => (
              <Link
                key={company.id}
                href={`/companies/${company.id}`}
                onClick={() => { setIsOpen(false); setQuery(''); }}
                className={[
                  'no-underline flex items-center justify-between px-4 py-3',
                  'hover:bg-[var(--paper-2)] transition-colors',
                  i !== results.length - 1 ? 'border-b border-[var(--rule)]' : '',
                ].join(' ')}
              >
                <div className="min-w-0 flex-1">
                  <p className="font-extrabold text-[var(--ink)] text-sm truncate">{company.name}</p>
                  {company.nip && (
                    <p className="text-[11px] text-[var(--ink-muted)] font-mono mt-0.5 tnum">
                      {t.card.nip}: {company.nip}
                    </p>
                  )}
                </div>
                <span className={`font-semibold text-base tnum ${riskTextClass(company.current_score)}`}>
                  {formatScore(company.current_score)}
                </span>
              </Link>
            ))
          ) : (
            <div className="px-4 py-5 text-center text-[var(--ink-muted)] text-sm">
              {t.search.noResults(query)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
