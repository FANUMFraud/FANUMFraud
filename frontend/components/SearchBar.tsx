'use client';

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { searchCompanies, type Company } from '@/lib/api';
import { getRiskLevel, formatScore } from '@/lib/risk';
import { useI18n } from '@/lib/i18n/I18nProvider';

const riskTextClass = (score: number) => {
  const r = getRiskLevel(score);
  if (r === 'high') return 'text-[var(--risk-high)]';
  if (r === 'medium') return 'text-[var(--risk-medium)]';
  return 'text-[var(--risk-low)]';
};

export default function SearchBar() {
  const { t } = useI18n();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Company[]>([]);
  const [loading, setLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

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
    if (query.trim().length < 2) {
      setResults([]);
      setIsOpen(false);
      return;
    }
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const data = await searchCompanies(query);
        setResults(data);
        setIsOpen(true);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 280);
    return () => clearTimeout(timer);
  }, [query]);

  return (
    <div ref={containerRef} className="relative w-full max-w-2xl mx-auto z-40">
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
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t.search.placeholder}
          aria-label={t.search.placeholder}
          className="doc-input pl-12 pr-14"
        />

        {loading && (
          <div className="absolute right-4">
            <div className="w-3.5 h-3.5 border-2 border-[var(--border)] border-t-[var(--ink)] rounded-full animate-spin" />
          </div>
        )}

        {!loading && query.trim().length > 0 && query.trim().length < 2 && (
          <span className="absolute right-4 text-[10px] uppercase tracking-[0.12em] text-[var(--ink-muted)] pointer-events-none">
            {t.search.hint}
          </span>
        )}
      </div>

      {isOpen && (
        <div
          className="absolute mt-[-1px] w-full bg-[var(--surface)] border border-[var(--ink)] border-t-0"
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
                  <p className="font-medium text-[var(--ink)] text-sm truncate">{company.name}</p>
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
