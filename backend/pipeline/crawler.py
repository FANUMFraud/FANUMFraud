import logging
from datetime import datetime, timezone
from time import mktime
from typing import Iterable

import feedparser
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Article

log = logging.getLogger(__name__)

RSS_FEEDS: dict[str, str] = {
    "money.pl": "https://www.money.pl/rss/",
    "businessinsider.com.pl": "https://businessinsider.com.pl/feed",
    "pb.pl": "https://www.pb.pl/rss/",
    "bankier.pl": "https://www.bankier.pl/rss/wiadomosci.xml",
    "pap.pl": "https://www.pap.pl/rss.xml",
}

FEED_TIMEOUT_SECONDS = 15


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
        log.warning("Feed parse warning source=%s err=%s", source, parsed.bozo_exception)

    entries: list[dict] = []
    for entry in parsed.entries:
        link = getattr(entry, "link", None)
        title = getattr(entry, "title", None)
        if not link or not title:
            continue
        entries.append(
            {
                "url": link.strip(),
                "title": title.strip(),
                "published_at": _entry_published(entry),
                "source": source,
            }
        )
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
    for source, url in RSS_FEEDS.items():
        try:
            collected.extend(fetch_feed(source, url))
        except Exception:
            log.exception("Failed to fetch feed source=%s", source)
    return filter_new(db, collected)
