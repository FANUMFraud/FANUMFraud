# Pydantic v2 schemas for FanumFraud API.

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _round_score(value: float | int | None) -> float:
    return round(float(value or 0.0), 2)


# Company


class CompanyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=512)
    nip: str | None = Field(None, pattern=r"^\d{10}$")
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


class CompanyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    nip: str | None
    current_score: float
    created_at: datetime
    ticker_gpw: str | None = None
    stock_price: StockPriceData | None = None
    momentum_7d: RiskMomentum | None = None
    momentum_30d: RiskMomentum | None = None
    sanctions: SanctionsCheck | None = None

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
    processed: bool
    created_at: datetime


class ArticleAnalyzeRequest(BaseModel):
    url: str | None = None
    content: str | None = None
    company_name: str


class ArticleAnalyzeResponse(BaseModel):
    ryzyko_score: float
    pewnosc: float
    kategoria: str
    waga_kontekstu: str
    uzasadnienie: str
    algorytm_wersja: str | None = None
    rozklad_score: dict[str, Any] | None = None
