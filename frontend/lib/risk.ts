export const HIGH_RISK_MAX_SCORE = 45;
export const MEDIUM_RISK_MAX_SCORE = 75;

export type RiskLevel = 'high' | 'medium' | 'low';

export function getRiskLevel(score: number): RiskLevel {
  if (score < HIGH_RISK_MAX_SCORE) return 'high';
  if (score < MEDIUM_RISK_MAX_SCORE) return 'medium';
  return 'low';
}

export function scoreDrop(previousScore: number, currentScore: number): number {
  return Math.max(0, previousScore - currentScore);
}
