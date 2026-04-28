import logging
import os
from datetime import datetime, timezone
from time import mktime
from typing import Iterable

import feedparser
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Article
from pipeline.watchlist import watchlist_rss_feeds

log = logging.getLogger(__name__)

BASE_RSS_FEEDS: dict[str, str] = {
    "money.pl": "https://www.money.pl/rss/",
    "businessinsider.com.pl": "https://businessinsider.com.pl/feed",
    "pb.pl": "https://www.pb.pl/rss/",
    "bankier.pl": "https://www.bankier.pl/rss/wiadomosci.xml",
    "pap.pl": "https://www.pap.pl/rss.xml",
}

WATCHLIST_FEEDS_ENABLED = os.getenv(
    "WATCHLIST_FEEDS_ENABLED", "true"
).strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

FEED_TIMEOUT_SECONDS = 15
WATCHLIST_MAX_ENTRIES_PER_FEED = int(os.getenv("WATCHLIST_MAX_ENTRIES_PER_FEED", "25"))


def _entry_published(entry) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        struct = getattr(entry, attr, None)
        if struct:
            try:
                return datetime.fromtimestamp(mktime(struct), tz=timezone.utc)
            except (TypeError, ValueError, OverflowError):
                continue
    return None


def fetch_feed(source: str, url: str) -> list[dict]:
    log.info("Fetching RSS feed source=%s url=%s", source, url)
    parsed = feedparser.parse(url, request_headers={"User-Agent": "FanumFraud/1.0"})

    if parsed.bozo:
        log.warning(
            "Feed parse warning source=%s err=%s", source, parsed.bozo_exception
        )

    entries: list[dict] = []
    for entry in parsed.entries:
        link = getattr(entry, "link", None)
        title = getattr(entry, "title", None)
        if not link or not title:
            continue
        summary = getattr(entry, "summary", None) or getattr(entry, "description", None)
        entries.append(
            {
                "url": link.strip(),
                "title": title.strip(),
                "published_at": _entry_published(entry),
                "source": source,
                "summary": str(summary).strip() if summary else None,
            }
        )
        if (
            source.startswith("watchlist:")
            and len(entries) >= WATCHLIST_MAX_ENTRIES_PER_FEED
        ):
            break
    log.info("Fetched %d entries source=%s", len(entries), source)
    return entries


def filter_new(db: Session, entries: Iterable[dict]) -> list[dict]:
    urls = [e["url"] for e in entries]
    if not urls:
        return []
    existing = set(
        db.execute(select(Article.url).where(Article.url.in_(urls))).scalars().all()
    )
    fresh = [e for e in entries if e["url"] not in existing]
    seen: set[str] = set()
    deduped: list[dict] = []
    for entry in fresh:
        if entry["url"] in seen:
            continue
        seen.add(entry["url"])
        deduped.append(entry)
    log.info("Filtered to %d new entries (from %d total)", len(deduped), len(urls))
    return deduped


def crawl_all_feeds(db: Session) -> list[dict]:
    collected: list[dict] = []
    feeds = dict(BASE_RSS_FEEDS)
    if WATCHLIST_FEEDS_ENABLED:
        feeds.update(watchlist_rss_feeds())

    for source, url in feeds.items():
        try:
            collected.extend(fetch_feed(source, url))
        except Exception:
            log.exception("Failed to fetch feed source=%s", source)
    return filter_new(db, collected)
