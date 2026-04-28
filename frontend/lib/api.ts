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
  status: 'listed' | 'clear' | 'unavailable' | string;
  available: boolean;
  lists: Array<{
    name: string;
    country: string;
    match_score: number;
    entity_id?: string;
    caption?: string;
    reason?: string;
  }>;
  confidence: number;
  source: string;
  reason?: string | null;
}

export interface Company {
  id: number;
  name: string;
  nip?: string | null;
  nip_check?: NipCheck | null;
  isin?: string | null;
  industry?: string | null;
  aliases?: string[];
  current_score: number;
  created_at: string;
  momentum_7d?: RiskMomentum | null;
  momentum_30d?: RiskMomentum | null;
  sanctions?: SanctionsCheck | null;
  evidence_quality?: EvidenceQuality | null;
  decision?: Decision | null;
  ticker_gpw?: string | null;
  stock_price?: {
    price: number;
    change_percent: number;
  } | null;
}

export interface NipCheck {
  status: 'valid' | 'invalid' | 'missing' | string;
  valid: boolean;
  normalized?: string | null;
  reason?: string | null;
  registry_status?: 'verified' | 'not_found' | 'unavailable' | 'not_checked' | string | null;
  registry_name?: string | null;
  registry_vat_status?: string | null;
  registry_source?: string | null;
  registry_checked_at?: string | null;
  registry_reason?: string | null;
}

export interface EvidenceQuality {
  score: number;
  level: 'high' | 'medium' | 'low' | string;
  articles_count: number;
  sources_count: number;
  official_sources_count: number;
  recent_articles_count: number;
  reasons: string[];
}

export interface Decision {
  level: 'proceed' | 'review' | 'block' | string;
  title: string;
  reasons: string[];
}

export interface LiveCompanySearchResponse {
  query: string;
  company_id: number;
  created: boolean;
  articles_found: number;
  articles_saved: number;
  articles_scored: number;
  articles_skipped: number;
  status: string;
  company: Company;
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
  language?: string | null;
  processed: boolean;
  created_at?: string;
  risk_score?: number | null;
  reputation_score?: number | null;
  category?: string | null;
  score_recorded_at?: string | null;
}

// ─── API Functions ────────────────────────────────────────────────────────────

export const getCompanies = (): Promise<Company[]> =>
  api.get<Company[]>('/companies').then((r) => r.data);

export const getCompanyScore = (
  id: number,
  params?: { days?: number }
): Promise<CompanyScoreResponse> =>
  api.get<CompanyScoreResponse>(`/companies/${id}/score`, { params }).then((r) => r.data);

export const getCompanyDetail = (id: number): Promise<Company> =>
  api.get<Company>(`/companies/${id}`).then((r) => r.data);

export const getCompanyArticles = (
  id: number,
  params?: { days?: number; limit?: number }
): Promise<Article[]> =>
  api.get<Article[]>(`/companies/${id}/articles`, { params }).then((r) => r.data);

export const searchCompanies = (q: string): Promise<Company[]> =>
  api.get<Company[]>(`/companies/search`, { params: { q } }).then((r) => r.data);

export const runLiveCompanySearch = (query: string): Promise<LiveCompanySearchResponse> =>
  api
    .post<LiveCompanySearchResponse>(
      '/companies/search/live',
      { query, limit: 12, force_refresh: false },
      { timeout: 60000 }
    )
    .then((r) => r.data);

export const getArticles = (): Promise<Article[]> =>
  api.get<Article[]>('/articles').then((r) => r.data);

export const getArticle = (id: number): Promise<Article> =>
  api.get<Article>(`/articles/${id}`).then((r) => r.data);
