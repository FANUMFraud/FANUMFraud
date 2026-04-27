'use client';

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import type { ScorePoint } from '@/lib/api';
import { getRiskLevel } from '@/lib/risk';
import { CATEGORY_META, normalizeCategory } from '@/lib/categories';

interface Props {
  history: ScorePoint[];
}

const getRiskColorClass = (score: number) => {
  const riskLevel = getRiskLevel(score);
  if (riskLevel === 'high') return 'text-red-400';
  if (riskLevel === 'medium') return 'text-yellow-400';
  return 'text-emerald-400';
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  const point: ScorePoint = payload[0].payload;
  const normalizedCategory = normalizeCategory(point.category);
  const cat = point.category ? CATEGORY_META[normalizedCategory].label : null;
  const riskColor = getRiskColorClass(point.score);

  return (
    <div className="bg-[#161e2e] border border-white/10 rounded-xl p-4 shadow-2xl text-sm min-w-[160px]">
      <p className="text-gray-400 text-xs mb-2">{label}</p>
      <p className="text-white font-bold text-2xl">{point.score.toFixed(0)}</p>
      {cat && (
        <p className={`${riskColor} text-xs font-medium mt-2 uppercase tracking-wide`}>{cat}</p>
      )}
    </div>
  );
};

export default function ScoreChart({ history }: Props) {
  const data = [...history]
    .sort((a, b) => new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime())
    .map((p) => ({
      ...p,
      date: new Date(p.recorded_at).toLocaleDateString('pl-PL', { day: '2-digit', month: '2-digit' }),
    }));

  if (data.length === 0) {
    return (
      <div className="h-72 flex items-center justify-center rounded-2xl border border-white/5 bg-[#0f1521] text-gray-600 text-sm">
        Brak historii scoringu
      </div>
    );
  }

  return (
    <div className="w-full h-72 rounded-2xl border border-white/5 bg-[#0f1521] p-6">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 4, bottom: 4, left: -20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
          <XAxis
            dataKey="date"
            stroke="transparent"
            tick={{ fill: '#6b7280', fontSize: 11 }}
            tickLine={false}
            dy={8}
          />
          <YAxis
            domain={[0, 100]}
            stroke="transparent"
            tick={{ fill: '#6b7280', fontSize: 11 }}
            tickLine={false}
          />
          <ReferenceLine y={75} stroke="rgba(245,158,11,0.25)" strokeDasharray="4 4" />
          <ReferenceLine y={45} stroke="rgba(239,68,68,0.25)" strokeDasharray="4 4" />
          <Tooltip content={<CustomTooltip />} cursor={{ stroke: 'rgba(255,255,255,0.08)', strokeWidth: 1 }} />
          <Line
            type="monotone"
            dataKey="score"
            stroke="#3b82f6"
            strokeWidth={2.5}
            dot={{ r: 3.5, fill: '#3b82f6', strokeWidth: 0 }}
            activeDot={{ r: 5, fill: '#fff', stroke: '#3b82f6', strokeWidth: 2 }}
            animationDuration={800}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
