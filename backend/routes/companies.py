# Company related API endpoints

import json
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from elastic import index_company, search_companies
from models import Article, Company, ScoreHistory
from schemas import (
    ArticleResponse,
    CompanyCreate,
    CompanyResponse,
    CompanyScoreResponse,
    ScorePoint,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/companies", tags=["companies"])


# GET /companies

@router.get("", response_model=list[CompanyResponse])
def list_companies(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    # Return all companies ordered by current_score ascending (worst first)
    return (
        db.query(Company)
        .order_by(Company.current_score.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )


# GET /companies/search

@router.get("/search")
def search(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    """
    Fuzzy search companies via Elasticsearch.

    Falls back to a LIKE query if ES is unreachable.
    """
    try:
        return search_companies(q)
    except Exception:
        logger.warning("Elasticsearch unavailable, falling back to SQL LIKE")
        pattern = f"%{q}%"
        rows = (
            db.query(Company)
            .filter(Company.name.ilike(pattern))
            .limit(20)
            .all()
        )
        return [
            {
                "id": r.id,
                "name": r.name,
                "nip": r.nip,
                "current_score": r.current_score,
            }
            for r in rows
        ]


# GET /companies/{company_id}

@router.get("/{company_id}", response_model=CompanyResponse)
def get_company(company_id: int, db: Session = Depends(get_db)):
    company = db.query(Company).get(company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


# GET /companies/{company_id}/score

@router.get("/{company_id}/score", response_model=CompanyScoreResponse)
def get_company_score(
    company_id: int,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    # Current score plus score history for the last *days*
    company = db.query(Company).get(company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    cutoff = datetime.utcnow() - timedelta(days=days)
    history = (
        db.query(ScoreHistory)
        .filter(
            ScoreHistory.company_id == company_id,
            ScoreHistory.recorded_at >= cutoff,
        )
        .order_by(ScoreHistory.recorded_at.asc())
        .all()
    )

    return CompanyScoreResponse(
        company_id=company.id,
        current_score=company.current_score,
        history=[ScorePoint.model_validate(h) for h in history],
    )


# GET /companies/{company_id}/articles

@router.get("/{company_id}/articles", response_model=list[ArticleResponse])
def get_company_articles(
    company_id: int,
    days: int = Query(90, ge=1, le=365),
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    company = db.query(Company).get(company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    cutoff = datetime.utcnow() - timedelta(days=days)
    article_ids_stmt = (
        select(ScoreHistory.article_id)
        .where(
            ScoreHistory.company_id == company_id,
            ScoreHistory.article_id.is_not(None),
            ScoreHistory.recorded_at >= cutoff,
        )
        .distinct()
    )

    return (
        db.query(Article)
        .filter(Article.id.in_(article_ids_stmt))
        .order_by(Article.published_at.desc(), Article.id.desc())
        .limit(limit)
        .all()
    )


# POST /companies

@router.post("", response_model=CompanyResponse, status_code=201)
def create_company(payload: CompanyCreate, db: Session = Depends(get_db)):
    """Register a new company and index it in Elasticsearch."""

    # NIP uniqueness check
    if payload.nip:
        existing = db.query(Company).filter(Company.nip == payload.nip).first()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Company with NIP {payload.nip} already exists (id={existing.id})",
            )

    company = Company(
        name=payload.name,
        nip=payload.nip,
        aliases=json.dumps(payload.aliases, ensure_ascii=False),
        current_score=100.0,
    )
    db.add(company)
    db.commit()
    db.refresh(company)

    try:
        index_company(company)
    except Exception:
        logger.warning("Failed to index company id=%d in ES", company.id, exc_info=True)

    return company
