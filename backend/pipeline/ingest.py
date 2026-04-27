import logging
from contextlib import contextmanager

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Article
from pipeline.crawler import crawl_all_feeds
from pipeline.scraper import scrape_article

log = logging.getLogger(__name__)

RISK_KEYWORDS: tuple[str, ...] = (
    "łapówka",
    "zarzuty",
    "korupcja",
    "sankcje",
    "pranie pieniędzy",
    "oszustwo",
    "wyłudzenie",
    "zarząd",
    "areszt",
    "prokuratura",
)


def contains_risk_keywords(text: str | None) -> bool:
    if not text:
        return False
    haystack = text.lower()
    return any(keyword in haystack for keyword in RISK_KEYWORDS)


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
    stats = {"crawled": 0, "scraped": 0, "saved_pending": 0, "saved_skipped": 0, "errors": 0}

    with _session() as db:
        new_entries = crawl_all_feeds(db)
        stats["crawled"] = len(new_entries)
        log.info("Ingest start: %d new candidate URLs", len(new_entries))

        for entry in new_entries:
            scraped = scrape_article(entry["url"], source=entry.get("source"))
            if not scraped:
                stats["errors"] += 1
                continue
            stats["scraped"] += 1

            payload = {
                "url": entry["url"],
                "title": scraped.get("title") or entry.get("title"),
                "content": scraped["content"],
                "source": entry.get("source") or scraped.get("source"),
                "published_at": entry.get("published_at") or scraped.get("published_at"),
            }

            has_risk = contains_risk_keywords(payload["content"]) or contains_risk_keywords(payload["title"])
            saved = _persist_article(db, payload, processed=not has_risk)
            if not saved:
                continue
            if has_risk:
                stats["saved_pending"] += 1
            else:
                stats["saved_skipped"] += 1

    log.info("Ingest done: %s", stats)
    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    run_ingest()
