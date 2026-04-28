# Company related API endpoints

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from analyzer import detect_article_language
from database import get_db
from elastic import index_company, search_companies
from identifiers import ensure_nip_registry, merge_nip_check, nip_check, normalize_nip
from models import Article, Company, ScoreHistory
from pipeline.company_registry import sync_companies_from_registry
from pipeline.live_search import run_live_company_search
from pipeline.watchlist import ensure_watchlist_companies
from reports import generate_risk_report
from sanctions import check_sanctions
from schemas import (
    ArticleResponse,
    CompanyCreate,
    CompanyResponse,
    Decision,
    EvidenceQuality,
    LiveCompanySearchRequest,
    LiveCompanySearchResponse,
    CompanySyncResponse,
    CompanyScoreResponse,
    NipCheck,
    RiskMomentum,
    SanctionsCheck,
    ScorePoint,
    StockPriceData,
    WatchlistBootstrapResponse,
)
from stock_fetcher import StooqPriceFetcher

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/companies", tags=["companies"])


# GET /companies


@router.get("", response_model=list[CompanyResponse])
def list_companies(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    include_empty: bool = Query(False),
    db: Session = Depends(get_db),
):
    query = db.query(Company)
    if not include_empty:
        has_history = exists().where(ScoreHistory.company_id == Company.id)
        query = query.filter(has_history)
    companies = (
        query.order_by(Company.current_score.asc())
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
        rows = db.query(Company).filter(Company.name.ilike(pattern)).limit(20).all()
        return [
            {
                "id": r.id,
                "name": r.name,
                "nip": r.nip,
                "current_score": r.current_score,
            }
            for r in rows
        ]


@router.post("/search/live", response_model=LiveCompanySearchResponse)
def live_company_search(
    payload: LiveCompanySearchRequest,
    db: Session = Depends(get_db),
):
    """Run ad-hoc online due-diligence search for a user-provided company."""
    try:
        stats = run_live_company_search(
            payload.query,
            limit=payload.limit,
            force_refresh=payload.force_refresh,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Live company search failed for query=%r", payload.query)
        raise HTTPException(status_code=502, detail="Live company search failed") from exc

    company = db.query(Company).get(stats.get("company_id"))
    if company is None:
        raise HTTPException(status_code=500, detail="Live search company not found")

    return LiveCompanySearchResponse(
        **stats,
        company=_company_response(company, db, refresh_registry=True),
    )


@router.post("/sync/online", response_model=CompanySyncResponse)
def sync_online_companies(limit: int = Query(300, ge=50, le=2000)):
    """
    Sync company registry from online source (GLEIF).

    This endpoint is safe to call repeatedly; existing entities are matched by
    LEI alias and fuzzy name.
    """
    try:
        return CompanySyncResponse.model_validate(
            sync_companies_from_registry(limit=limit)
        )
    except Exception:
        logger.exception("Online company sync failed")
        raise HTTPException(status_code=502, detail="Online company sync failed")


@router.post("/watchlist/bootstrap", response_model=WatchlistBootstrapResponse)
def bootstrap_watchlist_companies():
    try:
        return WatchlistBootstrapResponse.model_validate(ensure_watchlist_companies())
    except Exception:
        logger.exception("Watchlist bootstrap failed")
        raise HTTPException(status_code=502, detail="Watchlist bootstrap failed")


# GET /companies/{company_id}


@router.get("/{company_id}", response_model=CompanyResponse)
def get_company(company_id: int, db: Session = Depends(get_db)):
    company = db.query(Company).get(company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    response = _company_response(company, db, refresh_registry=True)

    # DODANE: Pobierz aktualną cenę akcji
    if company.ticker_gpw:
        try:
            stock_data = StooqPriceFetcher.fetch_current_price(company.ticker_gpw)
            if stock_data:
                response.stock_price = StockPriceData(
                    price=stock_data['price'],
                    change_percent=stock_data['price_change']
                )
        except Exception as e:
            logger.warning(f"Failed to fetch stock price for {company.ticker_gpw}: {e}")
            
    return response


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


def _company_response(
    company: Company,
    db: Session,
    *,
    refresh_registry: bool = False,
) -> CompanyResponse:
    sanctions = check_sanctions(company.name, company.nip)
    checksum_check = nip_check(company.nip)
    if checksum_check["status"] == "valid":
        registry_data = ensure_nip_registry(
            db, company, allow_remote=refresh_registry
        )
    else:
        registry_data = None
    nip_check_data = merge_nip_check(checksum_check, registry_data)
    evidence_quality_obj = _evidence_quality(db, company.id)
    momentum_7d = _risk_momentum(db, company.id, company.current_score, 7)
    momentum_30d = _risk_momentum(db, company.id, company.current_score, 30)
    
    # Get score history for top categories
    score_resp = get_company_score(company.id, days=90, db=db)
    
    # Calculate top categories for decision reasoning
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
    
    # Count articles
    article_ids_stmt = (
        select(ScoreHistory.article_id)
        .where(ScoreHistory.company_id == company.id, ScoreHistory.article_id.is_not(None))
        .distinct()
    )
    articles_count = db.query(Article).filter(Article.id.in_(article_ids_stmt)).count()
    
    # Compute decision
    decision_data = _due_diligence_decision(
        current_score=company.current_score,
        momentum_7d=momentum_7d.model_dump() if momentum_7d else None,
        sanctions=sanctions,
        nip_check_data=nip_check_data,
        evidence_quality=evidence_quality_obj.model_dump() if evidence_quality_obj else None,
        articles_count=articles_count,
        top_categories=top_categories,
    )
    
    return CompanyResponse(
        id=company.id,
        name=company.name,
        nip=company.nip,
        nip_check=NipCheck(**nip_check_data) if nip_check_data else None,
        isin=company.isin,
        industry=company.industry,
        aliases=_company_aliases(company),
        current_score=company.current_score,
        created_at=company.created_at,
        ticker_gpw=company.ticker_gpw,
        momentum_7d=momentum_7d,
        momentum_30d=momentum_30d,
        sanctions=SanctionsCheck(**sanctions),
        evidence_quality=evidence_quality_obj,
        decision=Decision(**decision_data) if decision_data else None,
    )


def _company_aliases(company: Company) -> list[str]:
    if not company.aliases:
        return []
    try:
        parsed = json.loads(company.aliases)
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item).strip() for item in parsed if str(item).strip()]


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


def _evidence_quality(db: Session, company_id: int, window_days: int = 180) -> EvidenceQuality:
    cutoff = datetime.utcnow() - timedelta(days=window_days)
    rows = (
        db.query(ScoreHistory, Article)
        .join(Article, Article.id == ScoreHistory.article_id)
        .filter(
            ScoreHistory.company_id == company_id,
            ScoreHistory.article_id.is_not(None),
            ScoreHistory.recorded_at >= cutoff,
        )
        .order_by(Article.published_at.desc(), ScoreHistory.id.desc())
        .all()
    )

    articles_by_id: dict[int, tuple[ScoreHistory, Article]] = {}
    for score, article in rows:
        if article.id not in articles_by_id:
            articles_by_id[article.id] = (score, article)

    if not articles_by_id:
        return EvidenceQuality(
            score=0.0,
            level="low",
            reasons=["No scored publications in the evidence window."],
        )

    pairs = list(articles_by_id.values())
    sources = {str(article.source or "").strip().lower() for _, article in pairs if article.source}
    source_tiers = [_source_tier(article.source) for _, article in pairs]
    official_count = sum(1 for tier in source_tiers if tier == "official")
    business_count = sum(1 for tier in source_tiers if tier == "business")
    recent_cutoff = datetime.utcnow() - timedelta(days=30)
    recent_count = sum(
        1 for _, article in pairs if article.published_at and article.published_at >= recent_cutoff
    )
    scored_count = sum(
        1 for score, _ in pairs if float(score.risk_score or 0.0) > 0.0 and score.category
    )

    value = 0.0
    value += min(len(pairs) * 10.0, 35.0)
    value += min(max(len(sources) - 1, 0) * 7.0, 21.0)
    value += min(official_count * 16.0, 24.0)
    value += min(business_count * 7.0, 14.0)
    value += min(recent_count * 4.0, 12.0)
    value += min(scored_count * 3.0, 12.0)
    value = min(value, 100.0)

    if value >= 70.0:
        level = "high"
    elif value >= 40.0:
        level = "medium"
    else:
        level = "low"

    reasons = [f"{len(pairs)} unique scored publication(s) in the last {window_days} days."]
    if official_count:
        reasons.append(f"{official_count} official or regulatory source(s) increase evidentiary strength.")
    elif business_count:
        reasons.append(f"{business_count} business media source(s) support the evidence base.")
    else:
        reasons.append("No official source found in the evidence window.")
    if len(sources) >= 2:
        reasons.append(f"Evidence comes from {len(sources)} distinct source(s).")
    if recent_count:
        reasons.append(f"{recent_count} publication(s) are recent enough for current due diligence.")

    return EvidenceQuality(
        score=value,
        level=level,
        articles_count=len(pairs),
        sources_count=len(sources),
        official_sources_count=official_count,
        recent_articles_count=recent_count,
        reasons=reasons[:4],
    )


def _source_tier(source: str | None) -> str:
    normalized = str(source or "").lower()
    official_patterns = ("knf", "uokik", "gov.pl", "prokuratura", "policja", "police", "sad", "court", "ofac", "europa.eu")
    business_patterns = ("money.pl", "bankier.pl", "businessinsider", "pb.pl", "parkiet", "rp.pl", "reuters", "bloomberg", "ft.com")
    low_trust_patterns = ("blog", "forum", "social", "twitter", "x.com", "facebook")
    if any(pattern in normalized for pattern in official_patterns):
        return "official"
    if any(pattern in normalized for pattern in business_patterns):
        return "business"
    if any(pattern in normalized for pattern in low_trust_patterns):
        return "low"
    return "standard"


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
    score_rows = (
        db.query(ScoreHistory)
        .join(Article, Article.id == ScoreHistory.article_id)
        .filter(
            ScoreHistory.company_id == company_id,
            ScoreHistory.article_id.is_not(None),
            ScoreHistory.recorded_at >= cutoff,
        )
        .order_by(Article.published_at.desc(), ScoreHistory.id.desc())
        .all()
    )

    deduped_scores: list[ScoreHistory] = []
    seen_article_ids: set[int] = set()
    for score in score_rows:
        if score.article_id is None or score.article_id in seen_article_ids:
            continue
        seen_article_ids.add(score.article_id)
        deduped_scores.append(score)
        if len(deduped_scores) >= limit:
            break

    if not deduped_scores:
        return []

    articles_by_id = {
        article.id: article
        for article in db.query(Article)
        .filter(Article.id.in_([score.article_id for score in deduped_scores]))
        .all()
    }

    return [
        _article_response(articles_by_id[score.article_id], score)
        for score in deduped_scores
        if score.article_id in articles_by_id
    ]


def _article_response(article: Article, score: ScoreHistory | None = None) -> ArticleResponse:
    return ArticleResponse(
        id=article.id,
        url=article.url,
        title=article.title,
        content=article.content,
        source=article.source,
        published_at=article.published_at,
        language=detect_article_language(f"{article.title or ''}\n{article.content or ''}"),
        processed=article.processed,
        created_at=article.created_at,
        risk_score=score.risk_score if score else None,
        reputation_score=score.score if score else None,
        category=score.category if score else None,
        score_recorded_at=score.recorded_at if score else None,
    )


def _reputation_risk_level(score: float | int | None) -> str:
    value = float(score or 0.0)
    if value < 45.0:
        return "high"
    if value < 75.0:
        return "medium"
    return "low"


def _due_diligence_decision(
    current_score: float,
    momentum_7d: dict[str, Any] | None,
    sanctions: dict[str, Any] | None,
    nip_check_data: dict[str, Any] | None,
    evidence_quality: dict[str, Any] | None,
    articles_count: int,
    top_categories: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    delta_7d = float((momentum_7d or {}).get("delta") or 0.0)
    top_category = (top_categories or [{}])[0].get("category") if top_categories else None
    evidence_articles = int((evidence_quality or {}).get("articles_count") or 0)
    evidence_score = float((evidence_quality or {}).get("score") or 0.0)
    nip_status = str((nip_check_data or {}).get("status") or "missing")
    nip_registry_status = str((nip_check_data or {}).get("registry_status") or "").lower()

    if sanctions and (sanctions.get("is_sanctioned") or sanctions.get("status") == "listed"):
        return {
            "level": "block",
            "title": "Block relationship",
            "reasons": [
                "Entity appears on a sanctions list.",
                "Compliance escalation is required before any action.",
            ],
        }

    if current_score < 45.0 or delta_7d <= -20.0:
        return {
            "level": "block",
            "title": "Do not proceed",
            "reasons": [
                "Reputation score is in the high-risk band or deteriorated rapidly.",
                f"Evidence window contains {articles_count} associated publication(s).",
            ],
        }

    registry_blocks_decision = (
        nip_status == "valid" and nip_registry_status == "not_found"
    )
    if (
        current_score < 75.0
        or delta_7d <= -5.0
        or (sanctions and sanctions.get("status") == "unavailable")
        or nip_status in {"missing", "invalid"}
        or registry_blocks_decision
        or evidence_articles <= 0
        or evidence_score < 40.0
    ):
        reasons = ["Manual review is required before onboarding or renewal."]
        if top_category:
            reasons.append(f"Dominant risk category: {top_category}.")
        if sanctions and sanctions.get("status") == "unavailable":
            reasons.append("Sanctions status has not been confirmed.")
        if nip_status == "invalid":
            reasons.append("NIP checksum or format is invalid.")
        if nip_status == "missing":
            reasons.append("NIP is missing, so entity identification is incomplete.")
        if registry_blocks_decision:
            reasons.append("The public MF VAT registry did not confirm this NIP.")
        elif nip_status == "valid" and nip_registry_status == "unavailable":
            reasons.append("The public MF VAT registry was unavailable; status not confirmed.")
        if evidence_articles <= 0:
            reasons.append("No online evidence was found for this entity.")
        elif evidence_score < 40.0:
            reasons.append("Evidence quality is low, so the assessment needs manual confirmation.")
        return {"level": "review", "title": "Manual review required", "reasons": reasons}

    return {
        "level": "proceed",
        "title": "Proceed",
        "reasons": [
            "No sanctions hit and low reputation risk profile.",
            "No material short-term deterioration detected.",
        ],
    }


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

    risk_level = _reputation_risk_level(company.current_score)

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

    evidence_quality = _evidence_quality(db, company.id).model_dump()

    checksum_check = nip_check(company.nip)
    registry_data = (
        ensure_nip_registry(db, company, allow_remote=True)
        if checksum_check["status"] == "valid"
        else None
    )
    nip_check_combined = merge_nip_check(checksum_check, registry_data)

    decision = _due_diligence_decision(
        current_score=company.current_score,
        momentum_7d=score_resp.momentum_7d.model_dump() if score_resp.momentum_7d else None,
        sanctions=sanctions_data,
        nip_check_data=nip_check_combined,
        evidence_quality=evidence_quality,
        articles_count=articles_count,
        top_categories=top_categories,
    )

    # Generate PDF
    pdf_bytes = generate_risk_report(
        company_id=company.id,
        company_name=company.name,
        nip=company.nip,
        nip_check=nip_check_combined,
        current_score=company.current_score,
        risk_level=risk_level,
        momentum_7d=score_resp.momentum_7d.model_dump() if score_resp.momentum_7d else None,
        momentum_30d=score_resp.momentum_30d.model_dump() if score_resp.momentum_30d else None,
        top_categories=top_categories,
        sanctions=sanctions_data,
        evidence_quality=evidence_quality,
        decision=decision,
        articles_count=articles_count,
    )

    if pdf_bytes is None:
        raise HTTPException(
            status_code=500,
            detail="PDF generation not available"
        )

    filename = f"risk_report_{company.id}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# POST /companies


@router.post("", response_model=CompanyResponse, status_code=201)
def create_company(payload: CompanyCreate, db: Session = Depends(get_db)):
    """Register a new company and index it in Elasticsearch."""
    normalized_nip = normalize_nip(payload.nip)

    # NIP uniqueness check
    if normalized_nip:
        existing = db.query(Company).filter(Company.nip == normalized_nip).first()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Company with NIP {normalized_nip} already exists (id={existing.id})",
            )

    company = Company(
        name=payload.name,
        nip=normalized_nip,
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

    return _company_response(company, db, refresh_registry=True)
