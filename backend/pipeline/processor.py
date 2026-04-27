from __future__ import annotations

import json
import logging
import re
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass
from difflib import SequenceMatcher
from datetime import UTC, datetime
from typing import Iterable

from sqlalchemy.orm import Session

try:
    from rapidfuzz import fuzz
except Exception:  # pragma: no cover - optional dependency in local dev
    fuzz = None  # type: ignore[assignment]

from analyzer import ArticleAnalyzer, ArticleInput, ArticleRiskAnalysis
from database import SessionLocal
from models import Article, Company, ScoreHistory
from scorer import ReputationScorer, RiskSignal

log = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 50
DEFAULT_HALF_LIFE_DAYS = 45.0
FUZZY_MATCH_THRESHOLD = 86.0
MIN_TEXT_MATCH_LENGTH = 5

_ANALYZER = ArticleAnalyzer()


@dataclass(frozen=True)
class CompanyAlias:
    company_id: int
    raw_value: str
    normalized_value: str


@contextmanager
def _session() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def process_pending_articles(batch_size: int = DEFAULT_BATCH_SIZE) -> dict[str, int]:
    stats = {
        "pending": 0,
        "processed": 0,
        "scored_companies": 0,
        "unmatched": 0,
        "errors": 0,
    }

    with _session() as db:
        pending_articles = (
            db.query(Article)
            .filter(Article.processed.is_(False))
            .order_by(Article.published_at.asc(), Article.id.asc())
            .limit(batch_size)
            .all()
        )
        stats["pending"] = len(pending_articles)

        if not pending_articles:
            return stats

        companies = db.query(Company).all()
        if not companies:
            log.info("Skipping processing: no companies in registry")
            return stats

        alias_index = _build_alias_index(companies)
        exact_lookup = _build_exact_lookup(alias_index)
        candidate_companies = _build_candidate_companies(companies)
        scorer = ReputationScorer(half_life_days=DEFAULT_HALF_LIFE_DAYS)

        for article in pending_articles:
            try:
                analysis = _analyze_article(article, candidate_companies)
                matched_company_ids = _resolve_company_ids(article, analysis, alias_index, exact_lookup)

                if not matched_company_ids:
                    article.processed = True
                    db.commit()
                    stats["processed"] += 1
                    stats["unmatched"] += 1
                    continue

                signal = _build_signal(analysis, article)
                category = _pick_category(analysis)

                for company_id in matched_company_ids:
                    new_score = _compute_company_score(db, scorer, company_id, signal)
                    db.add(
                        ScoreHistory(
                            company_id=company_id,
                            article_id=article.id,
                            score=new_score,
                            risk_score=signal.risk_score,
                            category=category,
                            recorded_at=_as_db_datetime(signal.timestamp),
                        )
                    )

                    company = db.get(Company, company_id)
                    if company is not None:
                        company.current_score = new_score
                    stats["scored_companies"] += 1

                article.processed = True
                db.commit()
                stats["processed"] += 1

            except Exception:
                db.rollback()
                stats["errors"] += 1
                log.exception("Failed to process article id=%s", article.id)

    log.info("Article processing completed: %s", stats)
    return stats


def _analyze_article(article: Article, candidate_companies: list[str]) -> ArticleRiskAnalysis:
    payload = ArticleInput(
        title=article.title or "",
        content=article.content or "",
        source=article.source,
        url=article.url,
        published_at=article.published_at,
        candidate_companies=candidate_companies,
    )
    return _ANALYZER.analyze(payload)


def _build_signal(analysis: ArticleRiskAnalysis, article: Article) -> RiskSignal:
    timestamp = article.published_at or datetime.now(UTC)
    sentiment = analysis.sentiment.value if hasattr(analysis.sentiment, "value") else str(analysis.sentiment)
    return RiskSignal(
        timestamp=timestamp,
        risk_score=analysis.risk_score,
        confidence=analysis.confidence,
        sentiment=sentiment,
        source_weight=1.0,
        article_id=article.id,
    )


def _pick_category(analysis: ArticleRiskAnalysis) -> str | None:
    if analysis.events:
        category = analysis.events[0].category
        return category.value if hasattr(category, "value") else str(category)
    if analysis.risk_keywords:
        category = analysis.risk_keywords[0].category
        return str(category).strip() or None
    return None


def _compute_company_score(
    db: Session,
    scorer: ReputationScorer,
    company_id: int,
    new_signal: RiskSignal,
) -> float:
    rows = (
        db.query(ScoreHistory)
        .filter(ScoreHistory.company_id == company_id)
        .order_by(ScoreHistory.recorded_at.asc(), ScoreHistory.id.asc())
        .all()
    )

    historical_signals = [_signal_from_history(row) for row in rows]
    point = scorer.point_at([*historical_signals, new_signal], as_of=new_signal.timestamp)
    return point.score


def _signal_from_history(row: ScoreHistory) -> RiskSignal:
    timestamp = row.recorded_at or datetime.now(UTC)
    inferred_sentiment = "negative" if row.risk_score > 0 else "neutral"
    return RiskSignal(
        timestamp=timestamp,
        risk_score=row.risk_score,
        confidence=0.7,
        sentiment=inferred_sentiment,
        source_weight=1.0,
        article_id=row.article_id,
    )


def _resolve_company_ids(
    article: Article,
    analysis: ArticleRiskAnalysis,
    alias_index: list[CompanyAlias],
    exact_lookup: dict[str, set[int]],
) -> list[int]:
    matched_ids: set[int] = set()

    for mention in analysis.companies_mentioned:
        values_to_match = [mention.name]
        if mention.normalized_name:
            values_to_match.append(mention.normalized_name)
        for value in values_to_match:
            company_id = _match_company_id(value, alias_index, exact_lookup)
            if company_id is not None:
                matched_ids.add(company_id)

    if matched_ids:
        return sorted(matched_ids)

    article_text = f"{article.title or ''}\n{article.content or ''}"
    fallback_ids = _match_from_article_text(article_text, alias_index)
    return sorted(fallback_ids)


def _match_company_id(
    value: str,
    alias_index: list[CompanyAlias],
    exact_lookup: dict[str, set[int]],
) -> int | None:
    normalized = _normalize_name(value)
    if not normalized:
        return None

    exact = exact_lookup.get(normalized)
    if exact:
        return sorted(exact)[0]

    best_company_id: int | None = None
    best_score = 0.0
    for alias in alias_index:
        score = _token_similarity(normalized, alias.normalized_value)
        if score > best_score:
            best_score = score
            best_company_id = alias.company_id

    if best_company_id is not None and best_score >= FUZZY_MATCH_THRESHOLD:
        return best_company_id
    return None


def _match_from_article_text(article_text: str, alias_index: list[CompanyAlias]) -> set[int]:
    normalized_text = _normalize_name(article_text)
    if not normalized_text:
        return set()

    found: set[int] = set()
    for alias in alias_index:
        needle = alias.normalized_value
        if len(needle) < MIN_TEXT_MATCH_LENGTH:
            continue
        pattern = rf"\b{re.escape(needle)}\b"
        if re.search(pattern, normalized_text):
            found.add(alias.company_id)
    return found


def _build_candidate_companies(companies: Iterable[Company], limit: int = 300) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()

    for company in companies:
        for raw in _iter_company_names(company):
            normalized = _normalize_name(raw)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            values.append(raw)
            if len(values) >= limit:
                return values

    return values


def _build_alias_index(companies: Iterable[Company]) -> list[CompanyAlias]:
    alias_index: list[CompanyAlias] = []
    for company in companies:
        seen_for_company: set[str] = set()
        for raw in _iter_company_names(company):
            normalized = _normalize_name(raw)
            if not normalized or normalized in seen_for_company:
                continue
            seen_for_company.add(normalized)
            alias_index.append(
                CompanyAlias(
                    company_id=company.id,
                    raw_value=raw,
                    normalized_value=normalized,
                )
            )
    return alias_index


def _build_exact_lookup(alias_index: Iterable[CompanyAlias]) -> dict[str, set[int]]:
    lookup: dict[str, set[int]] = {}
    for alias in alias_index:
        lookup.setdefault(alias.normalized_value, set()).add(alias.company_id)
    return lookup


def _iter_company_names(company: Company) -> list[str]:
    names: list[str] = []
    if company.name and company.name.strip():
        names.append(company.name.strip())

    aliases = _load_aliases(company.aliases)
    names.extend(alias for alias in aliases if alias.strip())
    return names


def _load_aliases(raw_aliases: str | None) -> list[str]:
    if not raw_aliases:
        return []

    if isinstance(raw_aliases, list):
        return [str(item).strip() for item in raw_aliases if str(item).strip()]

    try:
        parsed = json.loads(raw_aliases)
    except (TypeError, json.JSONDecodeError):
        return []

    if not isinstance(parsed, list):
        return []

    return [str(item).strip() for item in parsed if str(item).strip()]


def _normalize_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value))
    ascii_value = "".join(char for char in normalized if not unicodedata.combining(char)).lower()
    ascii_value = re.sub(r"[^a-z0-9\s\.\-&]", " ", ascii_value)
    return re.sub(r"\s+", " ", ascii_value).strip()


def _as_db_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _token_similarity(left: str, right: str) -> float:
    if fuzz is not None:
        return float(fuzz.token_set_ratio(left, right))
    return SequenceMatcher(a=left, b=right).ratio() * 100.0


__all__ = ["process_pending_articles"]
