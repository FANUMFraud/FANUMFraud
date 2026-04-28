from __future__ import annotations

import html
import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timezone
from time import mktime
from urllib.parse import quote_plus

import feedparser
from sqlalchemy.orm import Session

from analyzer import ArticleAnalyzer, ArticleInput
from database import SessionLocal
from elastic import index_company
from models import Article, Company, ScoreHistory
from pipeline.ingest import contains_risk_keywords
from pipeline.processor import _as_db_datetime, _build_signal, _compute_company_score, _pick_category
from scorer import ReputationScorer

log = logging.getLogger(__name__)

LIVE_SEARCH_WINDOW = "when:30d"
LIVE_RISK_TERMS = (
    "zarzuty",
    "sankcje",
    "korupcja",
    "pranie pieniędzy",
    "oszustwo",
    "wyłudzenie",
    "prokuratura",
    "UOKiK",
    "KNF",
    "postępowanie",
    "fraud",
    "sanctions",
    "corruption",
    "money laundering",
    "investigation",
    "prosecutor",
)

_ANALYZER = ArticleAnalyzer()


@dataclass(frozen=True)
class LiveEntry:
    url: str
    title: str
    content: str
    source: str
    published_at: datetime


def run_live_company_search(
    query: str,
    limit: int = 12,
    force_refresh: bool = False,
) -> dict:
    """Run an ad-hoc online due-diligence search for a user-provided company."""
    clean_query = _clean_query(query)
    if len(clean_query) < 2:
        raise ValueError("query must contain at least 2 characters")

    limit = max(1, min(int(limit), 25))
    stats = {
        "query": clean_query,
        "company_id": None,
        "created": False,
        "articles_found": 0,
        "articles_saved": 0,
        "articles_scored": 0,
        "articles_skipped": 0,
        "status": "completed",
    }

    with SessionLocal() as db:
        company, created = _upsert_company(db, clean_query)
        stats["company_id"] = company.id
        stats["created"] = created

        entries = _fetch_live_entries(clean_query, limit=limit)
        stats["articles_found"] = len(entries)

        articles: list[Article] = []
        for entry in entries:
            article, saved = _persist_live_article(db, entry, force_refresh=force_refresh)
            if article is None:
                stats["articles_skipped"] += 1
                continue
            articles.append(article)
            if saved:
                stats["articles_saved"] += 1

        scorer = ReputationScorer(half_life_days=45)
        for article in articles:
            if not force_refresh and _has_company_score(db, company.id, article.id):
                stats["articles_skipped"] += 1
                continue
            if not _mentions_company(article, clean_query, company):
                article.processed = True
                stats["articles_skipped"] += 1
                continue

            score_created = _score_live_article(db, company, article, scorer)
            article.processed = True
            if score_created:
                stats["articles_scored"] += 1

        db.commit()
        try:
            index_company(company)
        except Exception:
            log.warning("Failed to index live-search company id=%s", company.id, exc_info=True)

    return stats


def _fetch_live_entries(company_name: str, limit: int) -> list[LiveEntry]:
    risk_clause = " OR ".join(f'"{term}"' for term in LIVE_RISK_TERMS)
    search_query = f'"{company_name}" ({risk_clause}) {LIVE_SEARCH_WINDOW}'
    url = (
        "https://news.google.com/rss/search"
        f"?q={quote_plus(search_query)}&hl=pl&gl=PL&ceid=PL:pl"
    )

    parsed = feedparser.parse(url, request_headers={"User-Agent": "FanumFraud/1.0"})
    entries: list[LiveEntry] = []
    for raw in parsed.entries[:limit]:
        link = str(getattr(raw, "link", "") or "").strip()
        title = _strip_html(str(getattr(raw, "title", "") or "")).strip()
        if not link or not title:
            continue
        summary = _strip_html(
            str(getattr(raw, "summary", "") or getattr(raw, "description", "") or "")
        )
        content = f"{title}\n\n{summary}".strip()
        if len(content) < 40:
            continue
        entries.append(
            LiveEntry(
                url=link,
                title=title[:512],
                content=content,
                source=_entry_source(raw),
                published_at=_entry_published(raw) or datetime.now(UTC),
            )
        )
    return entries


def _upsert_company(db: Session, company_name: str) -> tuple[Company, bool]:
    normalized = _normalize(company_name)
    existing = db.query(Company).all()
    for company in existing:
        if _normalize(company.name) == normalized:
            _merge_company_alias(company, company_name)
            db.commit()
            db.refresh(company)
            return company, False

    company = Company(
        name=company_name,
        aliases=json.dumps([company_name], ensure_ascii=False),
        current_score=100.0,
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return company, True


def _merge_company_alias(company: Company, alias: str) -> None:
    aliases: list[str] = []
    if company.aliases:
        try:
            parsed = json.loads(company.aliases)
            if isinstance(parsed, list):
                aliases = [str(item) for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            aliases = []
    if _normalize(alias) not in {_normalize(item) for item in aliases}:
        aliases.append(alias)
        company.aliases = json.dumps(aliases, ensure_ascii=False)


def _persist_live_article(
    db: Session,
    entry: LiveEntry,
    force_refresh: bool,
) -> tuple[Article | None, bool]:
    existing = db.query(Article).filter(Article.url == entry.url).first()
    if existing is not None:
        if force_refresh:
            existing.title = entry.title
            existing.content = entry.content
            existing.source = entry.source
            existing.published_at = _as_db_datetime(entry.published_at)
            existing.processed = False
            db.commit()
            db.refresh(existing)
        return existing, False

    article = Article(
        url=entry.url,
        title=entry.title or "Brak tytulu",
        content=entry.content,
        source=entry.source,
        published_at=_as_db_datetime(entry.published_at),
        processed=False,
    )
    db.add(article)
    db.commit()
    db.refresh(article)
    return article, True


def _score_live_article(
    db: Session,
    company: Company,
    article: Article,
    scorer: ReputationScorer,
) -> bool:
    analysis = _ANALYZER.analyze(
        ArticleInput(
            title=article.title or "",
            content=article.content or "",
            source=article.source,
            url=article.url,
            published_at=article.published_at,
            candidate_companies=[company.name, *_company_aliases(company)],
        )
    )
    signal = _build_signal(analysis, article)
    category = _pick_category(analysis)

    if signal.risk_score <= 0 and not contains_risk_keywords(article.content):
        risk_score = 0.0
        score = company.current_score or 100.0
    else:
        risk_score = signal.risk_score
        score = _compute_company_score(db, scorer, company.id, signal, article.published_at)

    db.add(
        ScoreHistory(
            company_id=company.id,
            article_id=article.id,
            score=score,
            risk_score=risk_score,
            category=category,
            recorded_at=_as_db_datetime(article.published_at or datetime.now(UTC)),
        )
    )
    company.current_score = score
    return True


def _has_company_score(db: Session, company_id: int, article_id: int) -> bool:
    return (
        db.query(ScoreHistory)
        .filter(ScoreHistory.company_id == company_id, ScoreHistory.article_id == article_id)
        .first()
        is not None
    )


def _mentions_company(article: Article, query: str, company: Company) -> bool:
    haystack = _normalize(f"{article.title or ''} {article.content or ''}")
    names = [query, company.name, *_company_aliases(company)]
    return any(_normalize(name) and _normalize(name) in haystack for name in names)


def _company_aliases(company: Company) -> list[str]:
    if not company.aliases:
        return []
    try:
        parsed = json.loads(company.aliases)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item).strip() for item in parsed if str(item).strip()]


def _entry_published(entry) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        struct = getattr(entry, attr, None)
        if struct:
            try:
                return datetime.fromtimestamp(mktime(struct), tz=timezone.utc)
            except (TypeError, ValueError, OverflowError):
                continue
    return None


def _entry_source(entry) -> str:
    source = getattr(entry, "source", None)
    if source is not None:
        title = getattr(source, "title", None)
        if title:
            return f"google-news:{str(title).strip()}"
    return "google-news"


def _strip_html(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(without_tags)).strip()


def _clean_query(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())[:180]


def _normalize(value: str | None) -> str:
    lowered = str(value or "").strip().lower()
    lowered = re.sub(r"[^\w\s.&-]", " ", lowered, flags=re.UNICODE)
    return re.sub(r"\s+", " ", lowered).strip()


__all__ = ["run_live_company_search"]
