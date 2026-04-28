import logging
import re
import unicodedata
from contextlib import contextmanager
from datetime import datetime
from urllib.parse import urlparse

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from analyzer import CONFIRMED_PATTERNS, INVESTIGATED_PATTERNS, RISK_TERM_CONFIG
from database import SessionLocal
from models import Article
from pipeline.crawler import crawl_all_feeds
from pipeline.scraper import scrape_article
from pipeline.watchlist import WATCHLIST_COMPANIES

log = logging.getLogger(__name__)

RISK_REGEX_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        *(
            term_cfg.get("pattern")
            for category in RISK_TERM_CONFIG.values()
            for term_cfg in category.get("terms", [])
            if isinstance(term_cfg, dict)
        ),
        *INVESTIGATED_PATTERNS,
        *CONFIRMED_PATTERNS,
    ]
    if isinstance(pattern, str)
)

MIN_FALLBACK_SNIPPET_LENGTH = 120


def _to_ascii_lower(text: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return ascii_text.lower()


def _alias_key(value: str) -> str:
    normalized = _to_ascii_lower(value)
    normalized = re.sub(r"[^a-z0-9\s.&-]", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


WATCHLIST_ALIAS_KEYS: tuple[str, ...] = tuple(
    _alias_key(alias)
    for company in WATCHLIST_COMPANIES
    for alias in (company.name, *company.aliases)
    if _alias_key(alias)
)


def contains_risk_keywords(text: str | None) -> bool:
    if not text:
        return False
    haystack = _to_ascii_lower(text)
    return any(pattern.search(haystack) for pattern in RISK_REGEX_PATTERNS)


def contains_watchlist_mentions(title: str | None, content: str | None) -> bool:
    haystack = _alias_key(f"{title or ''} {content or ''}")
    if not haystack:
        return False
    return any(
        alias and re.search(rf"\b{re.escape(alias)}\b", haystack)
        for alias in WATCHLIST_ALIAS_KEYS
    )


def _feed_fallback_content(entry: dict) -> str | None:
    title = str(entry.get("title") or "").strip()
    summary = str(entry.get("summary") or "").strip()
    if not summary:
        return None
    content = f"{title}\n\n{summary}".strip()
    if len(content) < MIN_FALLBACK_SNIPPET_LENGTH:
        return None
    return content


def _prefer_feed_snippet(entry: dict) -> bool:
    source = str(entry.get("source") or "")
    if source.startswith("watchlist:"):
        return True
    url = str(entry.get("url") or "")
    host = (urlparse(url).hostname or "").lower()
    return host.endswith("news.google.com")


@contextmanager
def _session() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _persist_article(db: Session, payload: dict, processed: bool) -> bool:
    article = Article(
        url=payload["url"],
        title=payload.get("title"),
        content=payload.get("content"),
        source=payload.get("source"),
        published_at=payload.get("published_at"),
        processed=1 if processed else 0,
    )
    db.add(article)
    try:
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        log.info("Article already exists url=%s", payload["url"])
        return False
    except Exception:
        db.rollback()
        log.exception("Failed to persist article url=%s", payload["url"])
        return False


def run_ingest() -> dict:
    stats = {
        "crawled": 0,
        "scraped": 0,
        "saved_pending": 0,
        "saved_skipped": 0,
        "saved_from_feed_snippet": 0,
        "errors": 0,
    }

    with _session() as db:
        new_entries = crawl_all_feeds(db)
        stats["crawled"] = len(new_entries)
        log.info("Ingest start: %d new candidate URLs", len(new_entries))

        for entry in new_entries:
            scraped = None
            if not _prefer_feed_snippet(entry):
                scraped = scrape_article(entry["url"], source=entry.get("source"))
            if not scraped:
                fallback_content = _feed_fallback_content(entry)
                if not fallback_content:
                    stats["errors"] += 1
                    continue
                payload = {
                    "url": entry["url"],
                    "title": entry.get("title") or "Brak tytulu",
                    "content": fallback_content,
                    "source": entry.get("source") or "rss-snippet",
                    "published_at": entry.get("published_at") or datetime.utcnow(),
                }
                stats["saved_from_feed_snippet"] += 1
            else:
                stats["scraped"] += 1
                payload = {
                    "url": entry["url"],
                    "title": scraped.get("title")
                    or entry.get("title")
                    or "Brak tytulu",
                    "content": scraped["content"],
                    "source": entry.get("source") or scraped.get("source") or "unknown",
                    "published_at": entry.get("published_at")
                    or scraped.get("published_at")
                    or datetime.utcnow(),
                }

            has_risk = contains_risk_keywords(
                payload["content"]
            ) or contains_risk_keywords(payload["title"])
            watchlist_hit = contains_watchlist_mentions(
                payload.get("title"), payload.get("content")
            )
            should_process = has_risk or watchlist_hit

            saved = _persist_article(db, payload, processed=not should_process)
            if not saved:
                continue

            if should_process:
                stats["saved_pending"] += 1
            else:
                stats["saved_skipped"] += 1

    log.info("Ingest done: %s", stats)
    return stats


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    run_ingest()
