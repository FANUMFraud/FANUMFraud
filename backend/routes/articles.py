# Article related API endpoints.

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import Article
from schemas import (
    ArticleAnalyzeRequest,
    ArticleAnalyzeResponse,
    ArticleResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/articles", tags=["articles"])


# POST /articles/analyze

@router.post("/analyze", response_model=ArticleAnalyzeResponse)
def analyze_article(payload: ArticleAnalyzeRequest, db: Session = Depends(get_db)):
    """
    Run LLM sentiment/risk analysis on an article.

    Accepts either a URL (scrapes first) or raw content.
    Delegates to core.analyzer written by the Algorithm team.
    """
    content = payload.content

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

    # Delegate to the algorithm team's analyzer
    try:
        from core.analyzer import analyze_article as run_analysis

        result = run_analysis(content, payload.company_name)
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="Core analyzer module not deployed yet",
        )
    except Exception:
        logger.exception("LLM analysis failed")
        raise HTTPException(status_code=502, detail="LLM analysis error")

    return ArticleAnalyzeResponse(
        ryzyko_score=result.get("ryzyko_score", 0.0),
        pewnosc=result.get("pewnosc", 0.0),
        kategoria=result.get("kategoria", "neutralny"),
        waga_kontekstu=result.get("waga_kontekstu", "tlo"),
        uzasadnienie=result.get("uzasadnienie", ""),
    )


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

    return (
        query.order_by(Article.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


# GET /articles/{article_id}

@router.get("/{article_id}", response_model=ArticleResponse)
def get_article(article_id: int, db: Session = Depends(get_db)):
    article = db.query(Article).get(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return article
