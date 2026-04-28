from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.sql import func

from database import Base


# Firma w systemie monitorowania reputacji
class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    nip = Column(String, nullable=True)
    isin = Column(String, nullable=True)
    ticker_gpw = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    aliases = Column(Text, nullable=True)
    current_score = Column(Float, default=100.0)
    created_at = Column(DateTime, server_default=func.now())

    nip_registry_status = Column(String(32), nullable=True)
    nip_registry_name = Column(String(512), nullable=True)
    nip_registry_vat_status = Column(String(64), nullable=True)
    nip_registry_source = Column(String(64), nullable=True)
    nip_registry_checked_at = Column(DateTime, nullable=True)
    nip_registry_reason = Column(String(512), nullable=True)


# Artykuł prasowy
class Article(Base):
    __tablename__ = "articles"

    id: int = Column(Integer, primary_key=True)
    url: str = Column(String(2048), unique=True, nullable=False, index=True)
    title: str = Column(String(512), nullable=False)
    content: str = Column(Text, nullable=False)
    source: str = Column(String(255), nullable=False, index=True)
    published_at: datetime = Column(DateTime, nullable=False)
    processed: bool = Column(Boolean, default=False, index=True)
    created_at: datetime = Column(DateTime, server_default=func.now())


# Historia scoringu
class ScoreHistory(Base):
    __tablename__ = "scores_history"

    id: int = Column(Integer, primary_key=True)
    company_id: int = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    article_id: Optional[int] = Column(Integer, ForeignKey("articles.id"), nullable=True, index=True)
    score: float = Column(Float, nullable=False)
    risk_score: float = Column(Float, nullable=False)
    category: Optional[str] = Column(String(50), nullable=True)
    recorded_at: datetime = Column(DateTime, server_default=func.now(), index=True)


# Historia cen akcji na giełdzie
class StockPrice(Base):
    __tablename__ = "stock_prices"

    id: int = Column(Integer, primary_key=True)
    company_id: int = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    ticker: str = Column(String(20), nullable=False)
    price: float = Column(Float, nullable=False)
    price_change_percent: float = Column(Float, nullable=False)
    recorded_at: datetime = Column(DateTime, server_default=func.now(), index=True)

    __table_args__ = (UniqueConstraint('company_id', 'recorded_at'),)