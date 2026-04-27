'use client';

import { useState, useEffect, useRef } from 'react';
import { searchCompanies, type Company } from '@/lib/api';
import Link from 'next/link';
import { getRiskLevel } from '@/lib/risk';

const getRiskColor = (score: number) => {
  const riskLevel = getRiskLevel(score);
  if (riskLevel === 'high') return 'text-red-400';
  if (riskLevel === 'medium') return 'text-yellow-400';
  return 'text-emerald-400';
};

export default function SearchBar() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Company[]>([]);
  const [loading, setLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // Debounced search
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
    }, 300);

    return () => clearTimeout(timer);
  }, [query]);

  return (
    <div ref={containerRef} className="relative w-full max-w-2xl mx-auto z-40">
      {/* Input */}
      <div className="relative flex items-center">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="absolute left-5 w-5 h-5 text-gray-500 pointer-events-none"
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>

        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Szukaj firmy po nazwie lub NIP…"
          className="
            w-full py-4 pl-14 pr-12 text-base
            bg-[#0f1521] border border-white/10 rounded-2xl
            text-white placeholder:text-gray-600
            focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500/40
            transition-all duration-200
          "
        />

        {loading && (
          <div className="absolute right-5">
            <div className="w-4 h-4 border-2 border-gray-500 border-t-blue-400 rounded-full animate-spin" />
          </div>
        )}
      </div>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute mt-2 w-full bg-[#0f1521] border border-white/10 rounded-2xl shadow-2xl overflow-hidden">
          {results.length > 0 ? (
            results.map((company, i) => (
              <Link
                key={company.id}
                href={`/companies/${company.id}`}
                onClick={() => { setIsOpen(false); setQuery(''); }}
                className={`
                  flex items-center justify-between px-5 py-4
                  hover:bg-white/5 transition-colors
                  ${i !== results.length - 1 ? 'border-b border-white/5' : ''}
                `}
              >
                <div>
                  <p className="font-semibold text-white">{company.name}</p>
                  {company.nip && (
                    <p className="text-xs text-gray-500 font-mono mt-0.5">NIP: {company.nip}</p>
                  )}
                </div>
                <span className={`font-bold text-lg tabular-nums ${getRiskColor(company.current_score)}`}>
                  {company.current_score}
                </span>
              </Link>
            ))
          ) : (
            <div className="px-5 py-6 text-center text-gray-500 text-sm">
              Nie znaleziono firm pasujących do &quot;{query}&quot;
            </div>
          )}
        </div>
      )}
    </div>
  );
}
