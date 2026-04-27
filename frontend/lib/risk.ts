export const HIGH_RISK_MAX_SCORE = 45;
export const MEDIUM_RISK_MAX_SCORE = 75;

export type RiskLevel = 'high' | 'medium' | 'low';
export type MomentumTone = 'bad' | 'neutral' | 'good';

export function getRiskLevel(score: number): RiskLevel {
  if (score < HIGH_RISK_MAX_SCORE) return 'high';
  if (score < MEDIUM_RISK_MAX_SCORE) return 'medium';
  return 'low';
}

export function scoreDrop(previousScore: number, currentScore: number): number {
  return Math.max(0, previousScore - currentScore);
}

export function momentumTone(delta: number): MomentumTone {
  if (delta <= -5) return 'bad';
  if (delta >= 5) return 'good';
  return 'neutral';
}

export function momentumSymbol(delta: number): string {
  if (delta <= -5) return '↓';
  if (delta >= 5) return '↑';
  return '→';
}

export function formatMomentumDelta(delta: number): string {
  if (Math.abs(delta) < 0.005) return '0';
  return `${delta > 0 ? '+' : ''}${delta.toFixed(0)}`;
}

export function formatScore(score: number): string {
  if (!Number.isFinite(score)) return '—';
  const rounded = Math.round(score * 10) / 10;
  return Number.isInteger(rounded) ? rounded.toFixed(0) : rounded.toFixed(1);
}
