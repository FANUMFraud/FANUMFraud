# Pydantic v2 schemas for FanumFraud API.

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


# Company

class CompanyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=512)
    nip: str | None = Field(None, pattern=r"^\d{10}$")
    aliases: list[str] = Field(default_factory=list)


class CompanyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    nip: str | None
    current_score: float
    created_at: datetime


class ScorePoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    score: float
    risk_score: float
    category: str | None
    recorded_at: datetime


class CompanyScoreResponse(BaseModel):
    company_id: int
    current_score: float
    history: list[ScorePoint]


# Article

class ArticleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str | None
    title: str | None
    source: str | None
    published_at: datetime | None
    processed: int
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
