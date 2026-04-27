import Link from 'next/link';
import type { Company } from '@/lib/api';

interface Props {
  company: Company;
  animationDelay?: number;
}

export function getRiskLevel(score: number): 'high' | 'medium' | 'low' {
  if (score >= 80) return 'high';
  if (score >= 40) return 'medium';
  return 'low';
}

const riskConfig = {
  high: {
    label: 'Wysokie ryzyko',
    badge: 'bg-red-500/10 text-red-400 border border-red-500/20',
    border: 'border-red-500/30',
    glow: 'hover:shadow-red-500/10',
    scoreColor: 'text-red-400',
    bar: 'bg-red-500',
  },
  medium: {
    label: 'Średnie ryzyko',
    badge: 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20',
    border: 'border-yellow-500/30',
    glow: 'hover:shadow-yellow-500/10',
    scoreColor: 'text-yellow-400',
    bar: 'bg-yellow-500',
  },
  low: {
    label: 'Niskie ryzyko',
    badge: 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20',
    border: 'border-emerald-500/30',
    glow: 'hover:shadow-emerald-500/10',
    scoreColor: 'text-emerald-400',
    bar: 'bg-emerald-500',
  },
};

export default function CompanyCard({ company, animationDelay = 0 }: Props) {
  const risk = getRiskLevel(company.current_score);
  const cfg = riskConfig[risk];

  return (
    <Link
      href={`/companies/${company.id}`}
      className="block animate-fade-in-up"
      style={{ animationDelay: `${animationDelay}ms` }}
    >
      <div
        className={`
          h-full p-6 rounded-2xl border bg-[#0f1521] flex flex-col gap-5
          transition-all duration-300
          hover:scale-[1.02] hover:shadow-2xl
          ${cfg.border} ${cfg.glow}
        `}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <h3 className="text-lg font-bold text-white truncate leading-snug">
              {company.name}
            </h3>
            <p className="text-xs text-gray-500 font-mono mt-1">
              NIP: {company.nip ?? '—'}
            </p>
          </div>
          <span className={`shrink-0 text-xs font-semibold px-2.5 py-1 rounded-full ${cfg.badge}`}>
            {cfg.label}
          </span>
        </div>

        {/* Score */}
        <div className="flex items-end justify-between">
          <div>
            <p className="text-xs text-gray-500 uppercase tracking-widest mb-1">Risk Score</p>
            <p className={`text-5xl font-black tabular-nums ${cfg.scoreColor}`}>
              {company.current_score}
              <span className="text-2xl font-semibold text-gray-600">/100</span>
            </p>
          </div>
        </div>

        {/* Bar */}
        <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full ${cfg.bar} transition-all duration-700`}
            style={{ width: `${company.current_score}%` }}
          />
        </div>
      </div>
    </Link>
  );
}
