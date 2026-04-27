from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.sql import func

from database import Base


class Company(Base):
    """Model reprezentujący firmę w systemie monitorowania reputacji."""

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

    def __repr__(self) -> str:
        return (
            f"<Company(id={self.id}, name='{self.name}', "
            f"nip='{self.nip}', current_score={self.current_score})>"
        )


class Article(Base):
    """Model reprezentujący artykuł prasowy o firmie."""

    __tablename__ = "articles"

    id: int = Column(Integer, primary_key=True)
    url: str = Column(String(2048), unique=True, nullable=False, index=True)
    title: str = Column(String(512), nullable=False)
    content: str = Column(Text, nullable=False)
    source: str = Column(String(255), nullable=False, index=True)
    published_at: datetime = Column(DateTime, nullable=False)
    processed: bool = Column(Boolean, default=False, index=True)
    created_at: datetime = Column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return (
            f"<Article(id={self.id}, url='{self.url[:50]}...', "
            f"source='{self.source}', processed={self.processed})>"
        )


class ScoreHistory(Base):
    """Model reprezentujący historię zmian scoringu dla firmy."""

    __tablename__ = "scores_history"

    id: int = Column(Integer, primary_key=True)
    company_id: int = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    article_id: Optional[int] = Column(
        Integer, ForeignKey("articles.id"), nullable=True, index=True
    )
    score: float = Column(Float, nullable=False)
    risk_score: float = Column(Float, nullable=False)
    category: Optional[str] = Column(String(50), nullable=True)
    recorded_at: datetime = Column(DateTime, server_default=func.now(), index=True)

    def __repr__(self) -> str:
        return (
            f"<ScoreHistory(id={self.id}, company_id={self.company_id}, "
            f"score={self.score}, risk_score={self.risk_score}, "
            f"category='{self.category}')>"
        )