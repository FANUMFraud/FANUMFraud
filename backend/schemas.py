# Pydantic v2 schemas for FanumFraud API.

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# Company


class CompanyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=512)
    nip: str | None = Field(None, pattern=r"^\d{10}$")
    aliases: list[str] = Field(default_factory=list)


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


class ScorePoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    score: float
    risk_score: float
    category: str | None
    recorded_at: datetime


class CompanyScoreResponse(BaseModel):
    company_id: int
    current_score: float
    momentum_7d: RiskMomentum | None = None
    momentum_30d: RiskMomentum | None = None
    history: list[ScorePoint]


# Article


class ArticleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str | None
    title: str | None
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
