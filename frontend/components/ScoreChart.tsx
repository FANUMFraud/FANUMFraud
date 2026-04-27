'use client';

import {
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ComposedChart,
} from 'recharts';
import type { ScorePoint } from '@/lib/api';
import { getRiskLevel } from '@/lib/risk';
import { normalizeCategory } from '@/lib/categories';
import { useI18n } from '@/lib/i18n/I18nProvider';
import { useTheme } from '@/lib/theme/ThemeProvider';

interface Props {
  history: ScorePoint[];
}

const lightChart = {
  line: '#003064',
  dotStroke: '#003064',
  dotFill: '#ffffff',
  activeDotFill: '#003064',
  axis: 'rgba(17,24,39,0.35)',
  axisTick: '#526273',
  grid: 'rgba(17,24,39,0.10)',
  cursor: 'rgba(0,48,100,0.35)',
  refMedium: 'rgba(138,90,0,0.45)',
  refMediumLabel: '#8a5a00',
  refHigh: 'rgba(176,0,32,0.45)',
  refHighLabel: '#b00020',
};

const darkChart = {
  line: '#7eb6f0',
  dotStroke: '#7eb6f0',
  dotFill: '#0b1220',
  activeDotFill: '#7eb6f0',
  axis: 'rgba(238,244,251,0.28)',
  axisTick: '#a1afc1',
  grid: 'rgba(238,244,251,0.08)',
  cursor: 'rgba(126,182,240,0.35)',
  refMedium: 'rgba(212,165,90,0.55)',
  refMediumLabel: '#d4a55a',
  refHigh: 'rgba(232,117,131,0.55)',
  refHighLabel: '#e87583',
};

const riskColor = (score: number, dark: boolean) => {
  const r = getRiskLevel(score);
  if (r === 'high') return dark ? '#e87583' : '#a51c2e';
  if (r === 'medium') return dark ? '#d4a55a' : '#8a5a00';
  return dark ? '#6dba8a' : '#1f5e3a';
};

interface TooltipPayload { payload: ScorePoint; }
interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayload[];
  label?: string;
  categoryLabel: (key: string | null | undefined) => string | null;
  dark: boolean;
}

function CustomTooltip({ active, payload, label, categoryLabel, dark }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  const cat = categoryLabel(point.category);

  return (
    <div
      className="bg-[var(--surface)] border border-[var(--ink)] px-3 py-2 text-sm min-w-[150px]"
      style={{ borderRadius: 0 }}
    >
      <p className="text-[10px] mb-1 uppercase tracking-[0.12em] text-[var(--ink-muted)]">{label}</p>
      <p
        className="font-semibold text-2xl tnum leading-none"
        style={{ color: riskColor(point.score, dark) }}
      >
        {point.score.toFixed(0)}
      </p>
      {cat && (
        <p className="text-[11px] mt-1 text-[var(--ink-2)] border-t border-[var(--rule)] pt-1.5">
          {cat}
        </p>
      )}
    </div>
  );
}

export default function ScoreChart({ history }: Props) {
  const { t, locale } = useI18n();
  const { theme } = useTheme();
  const dark = theme === 'dark';
  const c = dark ? darkChart : lightChart;
  const dateTag = locale === 'pl' ? 'pl-PL' : 'en-GB';

  const data = [...history]
    .sort((a, b) => new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime())
    .map((p) => ({
      ...p,
      date: new Date(p.recorded_at).toLocaleDateString(dateTag, {
        day: '2-digit',
        month: '2-digit',
      }),
    }));

  const categoryLabel = (key: string | null | undefined) => {
    if (!key) return null;
    const norm = normalizeCategory(key);
    return t.categories[norm];
  };

  if (data.length === 0) {
    return (
      <div
        className="h-72 flex items-center justify-center bg-[var(--surface)] border border-[var(--border)] text-[var(--ink-muted)] text-sm"
        style={{ borderRadius: '2px' }}
      >
        {t.detail.chartEmpty}
      </div>
    );
  }

  return (
    <div className="w-full h-80 bg-[var(--surface)] border border-[var(--border)] border-t-4 border-t-[var(--gov-blue)] p-5">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 10, right: 14, bottom: 0, left: -16 }}>
          <CartesianGrid stroke={c.grid} vertical={false} />
          <XAxis
            dataKey="date"
            stroke={c.axis}
            tick={{ fill: c.axisTick, fontSize: 11 }}
            tickLine={{ stroke: c.axis }}
            dy={6}
          />
          <YAxis
            domain={[0, 100]}
            stroke={c.axis}
            tick={{ fill: c.axisTick, fontSize: 11 }}
            tickLine={{ stroke: c.axis }}
          />
          <ReferenceLine
            y={75}
            stroke={c.refMedium}
            strokeDasharray="3 4"
            label={{ value: '75', fill: c.refMediumLabel, fontSize: 10, position: 'right' }}
          />
          <ReferenceLine
            y={45}
            stroke={c.refHigh}
            strokeDasharray="3 4"
            label={{ value: '45', fill: c.refHighLabel, fontSize: 10, position: 'right' }}
          />
          <Tooltip
            content={<CustomTooltip categoryLabel={categoryLabel} dark={dark} />}
            cursor={{ stroke: c.cursor, strokeWidth: 1, strokeDasharray: '2 3' }}
          />
          <Line
            type="linear"
            dataKey="score"
            stroke={c.line}
            strokeWidth={1.5}
            dot={{ r: 3, fill: c.dotFill, stroke: c.dotStroke, strokeWidth: 1.5 }}
            activeDot={{ r: 5, fill: c.activeDotFill, stroke: c.dotFill, strokeWidth: 2 }}
            animationDuration={500}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
