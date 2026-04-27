import axios from 'axios';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
  timeout: 10000,
});

// ─── Types ────────────────────────────────────────────────────────────────────

export interface SanctionsCheck {
  is_sanctioned: boolean;
  lists: Array<{
    name: string;
    country: string;
    match_score: number;
    entity_id?: string;
  }>;
  confidence: number;
  source: string;
}

export interface Company {
  id: number;
  name: string;
  nip?: string | null;
  current_score: number;
  created_at: string;
  momentum_7d?: RiskMomentum | null;
  momentum_30d?: RiskMomentum | null;
  sanctions?: SanctionsCheck | null;
}

export type MomentumLabel =
  | 'rapid_deterioration'
  | 'declining'
  | 'stable'
  | 'recovering'
  | 'strong_recovery';

export interface RiskMomentum {
  window_days: number;
  current_score: number;
  past_score: number;
  delta: number;
  label: MomentumLabel;
}

export interface ScorePoint {
  score: number;
  risk_score?: number;
  recorded_at: string;
  category?: string | null;
}

export interface CompanyScoreResponse {
  company_id: number;
  current_score: number;
  momentum_7d?: RiskMomentum | null;
  momentum_30d?: RiskMomentum | null;
  history: ScorePoint[];
}

export interface Article {
  id: number;
  url?: string | null;
  title?: string | null;
  content?: string | null;
  source?: string | null;
  published_at?: string | null;
  processed: boolean;
  created_at?: string;
}

// ─── API Functions ────────────────────────────────────────────────────────────

export const getCompanies = (): Promise<Company[]> =>
  api.get<Company[]>('/companies').then((r) => r.data);

export const getCompanyScore = (id: number): Promise<CompanyScoreResponse> =>
  api.get<CompanyScoreResponse>(`/companies/${id}/score`).then((r) => r.data);

export const getCompanyDetail = (id: number): Promise<Company> =>
  api.get<Company>(`/companies/${id}`).then((r) => r.data);

export const getCompanyArticles = (
  id: number,
  params?: { days?: number; limit?: number }
): Promise<Article[]> =>
  api.get<Article[]>(`/companies/${id}/articles`, { params }).then((r) => r.data);

export const searchCompanies = (q: string): Promise<Company[]> =>
  api.get<Company[]>(`/companies/search`, { params: { q } }).then((r) => r.data);

export const getArticles = (): Promise<Article[]> =>
  api.get<Article[]>('/articles').then((r) => r.data);

export const getArticle = (id: number): Promise<Article> =>
  api.get<Article>(`/articles/${id}`).then((r) => r.data);
