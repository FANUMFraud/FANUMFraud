from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from database import Base

class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    nip = Column(String, unique=True, nullable=True)
    aliases = Column(Text)
    current_score = Column(Float, default=100.0)
    created_at = Column(DateTime, server_default=func.now())

class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True)
    url = Column(String, unique=True)
    title = Column(String)
    content = Column(Text)
    source = Column(String)
    published_at = Column(DateTime)
    processed = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())

class ScoreHistory(Base):
    __tablename__ = "scores_history"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    score = Column(Float)
    risk_score = Column(Float)
    category = Column(String, default="neutralny")
    article_id = Column(Integer, ForeignKey("articles.id"))
    recorded_at = Column(DateTime, server_default=func.now())
