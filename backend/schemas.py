# Pydantic v2 schemas for FanumFraud API.

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _round_score(value: float | int | None) -> float:
    return round(float(value or 0.0), 2)


# Company


class CompanyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=512)
    nip: str | None = Field(None, max_length=32)
    aliases: list[str] = Field(default_factory=list)


class LiveCompanySearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=180)
    limit: int = Field(default=12, ge=1, le=25)
    force_refresh: bool = False


class StockPriceData(BaseModel):
    """Dane giełdowe dla firmy"""
    model_config = ConfigDict(from_attributes=True)
    
    price: float
    change_percent: float

class RiskMomentum(BaseModel):
    window_days: int
    current_score: float
    past_score: float
    delta: float
    label: str

    @field_validator("current_score", "past_score", "delta", mode="before")
    @classmethod
    def _round_momentum_scores(cls, value: float | int | None) -> float:
        return _round_score(value)


class SanctionsCheck(BaseModel):
    is_sanctioned: bool
    status: str = "unknown"
    available: bool = True
    lists: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.0
    source: str = "unknown"
    reason: str | None = None


class NipCheck(BaseModel):
    status: str
    valid: bool
    normalized: str | None = None
    reason: str | None = None
    registry_status: str | None = None
    registry_name: str | None = None
    registry_vat_status: str | None = None
    registry_source: str | None = None
    registry_checked_at: datetime | None = None
    registry_reason: str | None = None


class EvidenceQuality(BaseModel):
    score: float
    level: str
    articles_count: int = 0
    sources_count: int = 0
    official_sources_count: int = 0
    recent_articles_count: int = 0
    reasons: list[str] = Field(default_factory=list)

    @field_validator("score", mode="before")
    @classmethod
    def _round_evidence_score(cls, value: float | int | None) -> float:
        return _round_score(value)


class Decision(BaseModel):
    level: str = Field(..., description="Decision level: proceed, review, or block")
    title: str = Field(..., description="Decision title")
    reasons: list[str] = Field(default_factory=list, description="List of reasons for the decision")


class CompanyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    nip: str | None
    nip_check: NipCheck | None = None
    isin: str | None = None
    industry: str | None = None
    aliases: list[str] = Field(default_factory=list)
    current_score: float
    created_at: datetime
    ticker_gpw: str | None = None
    stock_price: StockPriceData | None = None
    momentum_7d: RiskMomentum | None = None
    momentum_30d: RiskMomentum | None = None
    sanctions: SanctionsCheck | None = None
    evidence_quality: EvidenceQuality | None = None
    decision: Decision | None = None

    @field_validator("current_score", mode="before")
    @classmethod
    def _round_current_score(cls, value: float | int | None) -> float:
        return _round_score(value)


class LiveCompanySearchResponse(BaseModel):
    query: str
    company_id: int
    created: bool
    articles_found: int
    articles_saved: int
    articles_scored: int
    articles_skipped: int
    status: str
    company: CompanyResponse


class ScorePoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    score: float
    risk_score: float
    category: str | None
    recorded_at: datetime

    @field_validator("score", "risk_score", mode="before")
    @classmethod
    def _round_score_points(cls, value: float | int | None) -> float:
        return _round_score(value)


class CompanyScoreResponse(BaseModel):
    company_id: int
    current_score: float
    momentum_7d: RiskMomentum | None = None
    momentum_30d: RiskMomentum | None = None
    history: list[ScorePoint]

    @field_validator("current_score", mode="before")
    @classmethod
    def _round_current_score(cls, value: float | int | None) -> float:
        return _round_score(value)


class CompanySyncResponse(BaseModel):
    fetched: int
    created: int
    updated: int
    skipped: int
    errors: int


class WatchlistBootstrapResponse(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: int


# Article


class ArticleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str | None
    title: str | None
    content: str | None = None
    source: str | None
    published_at: datetime | None
    language: str | None = None
    processed: bool
    created_at: datetime
    risk_score: float | None = None
    reputation_score: float | None = None
    category: str | None = None
    score_recorded_at: datetime | None = None

    @field_validator("risk_score", "reputation_score", mode="before")
    @classmethod
    def _round_article_scores(cls, value: float | int | None) -> float | None:
        if value is None:
            return None
        return _round_score(value)


class ArticleAnalyzeRequest(BaseModel):
    url: str | None = None
    content: str | None = None
    company_name: str


class ArticleAnalyzeResponse(BaseModel):
    ryzyko_score: float
    pewnosc: float
    jezyk: str = "unknown"
    kategoria: str
    waga_kontekstu: str
    uzasadnienie: str
    algorytm_wersja: str | None = None
    rozklad_score: dict[str, Any] | None = None
