# Company related API endpoints

import json
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from elastic import index_company, search_companies
from models import Article, Company, ScoreHistory
from reports import generate_risk_report
from sanctions import check_sanctions
from schemas import (
    ArticleResponse,
    CompanyCreate,
    CompanyResponse,
    CompanyScoreResponse,
    RiskMomentum,
    SanctionsCheck,
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
    companies = (
        db.query(Company)
        .order_by(Company.current_score.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [_company_response(company, db) for company in companies]


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
    return _company_response(company, db)


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
        momentum_7d=_risk_momentum(db, company.id, company.current_score, 7),
        momentum_30d=_risk_momentum(db, company.id, company.current_score, 30),
        history=[ScorePoint.model_validate(h) for h in history],
    )


def _company_response(company: Company, db: Session) -> CompanyResponse:
    sanctions = check_sanctions(company.name, company.nip)
    return CompanyResponse(
        id=company.id,
        name=company.name,
        nip=company.nip,
        current_score=company.current_score,
        created_at=company.created_at,
        momentum_7d=_risk_momentum(db, company.id, company.current_score, 7),
        momentum_30d=_risk_momentum(db, company.id, company.current_score, 30),
        sanctions=SanctionsCheck(**sanctions),
    )


def _risk_momentum(
    db: Session,
    company_id: int,
    current_score: float,
    window_days: int,
) -> RiskMomentum | None:
    cutoff = datetime.utcnow() - timedelta(days=window_days)
    past_point = (
        db.query(ScoreHistory)
        .filter(
            ScoreHistory.company_id == company_id,
            ScoreHistory.recorded_at <= cutoff,
        )
        .order_by(ScoreHistory.recorded_at.desc(), ScoreHistory.id.desc())
        .first()
    )
    if past_point is None:
        past_point = (
            db.query(ScoreHistory)
            .filter(ScoreHistory.company_id == company_id)
            .order_by(ScoreHistory.recorded_at.asc(), ScoreHistory.id.asc())
            .first()
        )
    if past_point is None:
        return None

    delta = round(float(current_score) - float(past_point.score), 2)
    return RiskMomentum(
        window_days=window_days,
        current_score=round(float(current_score), 2),
        past_score=round(float(past_point.score), 2),
        delta=delta,
        label=_momentum_label(delta),
    )


def _momentum_label(delta: float) -> str:
    if delta <= -20.0:
        return "rapid_deterioration"
    if delta <= -5.0:
        return "declining"
    if delta < 5.0:
        return "stable"
    if delta < 20.0:
        return "recovering"
    return "strong_recovery"


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


# GET /companies/{company_id}/export

@router.get("/{company_id}/export")
def export_company_report(
    company_id: int,
    db: Session = Depends(get_db),
):
    """Export company risk assessment as PDF report."""
    company = db.query(Company).get(company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    # Get score history
    score_resp = get_company_score(company_id, days=90, db=db)
    
    # Count articles
    article_ids_stmt = (
        select(ScoreHistory.article_id)
        .where(ScoreHistory.company_id == company_id, ScoreHistory.article_id.is_not(None))
        .distinct()
    )
    articles_count = db.query(Article).filter(Article.id.in_(article_ids_stmt)).count()

    # Get risk level
    from analyzer import risk_level_from_score
    risk_level = risk_level_from_score(company.current_score)

    # Get sanctions
    sanctions_data = check_sanctions(company.name, company.nip)

    # Get top categories
    top_categories = None
    if score_resp.history:
        categories: dict[str, float] = {}
        for point in score_resp.history:
            if point.category:
                categories[point.category] = categories.get(point.category, 0) + point.risk_score
        top_categories = [
            {"category": cat, "points": points}
            for cat, points in sorted(categories.items(), key=lambda x: x[1], reverse=True)
        ]

    # Generate PDF
    pdf_bytes = generate_risk_report(
        company_id=company.id,
        company_name=company.name,
        nip=company.nip,
        current_score=company.current_score,
        risk_level=risk_level.value,
        momentum_7d=score_resp.momentum_7d.model_dump() if score_resp.momentum_7d else None,
        momentum_30d=score_resp.momentum_30d.model_dump() if score_resp.momentum_30d else None,
        top_categories=top_categories,
        sanctions=sanctions_data,
        articles_count=articles_count,
    )

    if pdf_bytes is None:
        raise HTTPException(
            status_code=500,
            detail="PDF generation not available"
        )

    filename = f"risk_report_{company.id}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    return FileResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
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
