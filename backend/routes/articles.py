# Article related API endpoints.

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from analyzer import ArticleAnalyzer, ArticleInput
from database import get_db
from models import Article
from schemas import (
    ArticleAnalyzeRequest,
    ArticleAnalyzeResponse,
    ArticleResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/articles", tags=["articles"])
article_analyzer = ArticleAnalyzer()


# POST /articles/analyze


@router.post("/analyze", response_model=ArticleAnalyzeResponse)
def analyze_article(payload: ArticleAnalyzeRequest):
    """
    Run sentiment/risk analysis on an article.

    Accepts either a URL (scrapes first) or raw content and analyzes
    with the local ArticleAnalyzer implementation.
    """
    content = payload.content
    title = ""
    source: str | None = None
    published_at: datetime | None = None

    # If URL given but no content, scrape it
    if not content and payload.url:
        try:
            from pipeline.scraper import scrape_article

            scraped = scrape_article(payload.url)
            if scraped is None or not scraped.get("content"):
                raise HTTPException(
                    status_code=422,
                    detail="Could not extract text from the provided URL",
                )
            content = scraped["content"]
            title = scraped.get("title") or ""
            source = scraped.get("source")
            published_at = scraped.get("published_at")
        except ImportError:
            raise HTTPException(
                status_code=501,
                detail="Pipeline scraper not available — provide content directly",
            )

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Either 'url' or 'content' must be provided",
        )

    candidate_companies = (
        [payload.company_name.strip()] if payload.company_name.strip() else []
    )

    try:
        analysis = article_analyzer.analyze(
            ArticleInput(
                title=title,
                content=content,
                source=source,
                url=payload.url,
                published_at=published_at,
                candidate_companies=candidate_companies,
            )
        )
    except Exception:
        logger.exception("LLM analysis failed")
        raise HTTPException(status_code=502, detail="Article analysis error")

    category = _analysis_category(analysis)
    context_weight = _context_weight(analysis.risk_level.value)

    return ArticleAnalyzeResponse(
        ryzyko_score=analysis.risk_score,
        pewnosc=analysis.confidence,
        kategoria=category,
        waga_kontekstu=context_weight,
        uzasadnienie=analysis.summary,
        algorytm_wersja=analysis.algorithm_version,
        rozklad_score=analysis.score_breakdown,
    )


def _analysis_category(analysis) -> str:
    if analysis.events:
        first_category = analysis.events[0].category
        return (
            first_category.value
            if hasattr(first_category, "value")
            else str(first_category)
        )
    if analysis.risk_keywords:
        return str(analysis.risk_keywords[0].category)
    return analysis.risk_level.value


def _context_weight(risk_level: str) -> str:
    if risk_level in {"critical", "high"}:
        return "wysoki"
    if risk_level == "medium":
        return "sredni"
    return "niski"


# GET /articles


@router.get("", response_model=list[ArticleResponse])
def list_articles(
    processed: bool | None = None,
    source: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    # List articles with optional filters.
    query = db.query(Article)

    if processed is not None:
        query = query.filter(Article.processed == processed)
    if source is not None:
        query = query.filter(Article.source == source)
    if date_from is not None:
        query = query.filter(Article.published_at >= date_from)
    if date_to is not None:
        query = query.filter(Article.published_at <= date_to)

    return query.order_by(Article.created_at.desc()).offset(skip).limit(limit).all()


# GET /articles/{article_id}


@router.get("/{article_id}", response_model=ArticleResponse)
def get_article(article_id: int, db: Session = Depends(get_db)):
    article = db.query(Article).get(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return article
