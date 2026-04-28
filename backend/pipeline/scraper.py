import logging
from datetime import datetime, timezone

import trafilatura
from trafilatura.settings import use_config

log = logging.getLogger(__name__)

MIN_CONTENT_LENGTH = 200
DOWNLOAD_TIMEOUT_SECONDS = 20

_TRAFILATURA_CONFIG = use_config()
_TRAFILATURA_CONFIG.set("DEFAULT", "DOWNLOAD_TIMEOUT", str(DOWNLOAD_TIMEOUT_SECONDS))
_TRAFILATURA_CONFIG.set("DEFAULT", "USER_AGENTS", "FanumFraud/1.0")


def _parse_iso_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None


def scrape_article(url: str, source: str | None = None) -> dict | None:
    log.debug("Scraping url=%s", url)
    try:
        downloaded = trafilatura.fetch_url(url, config=_TRAFILATURA_CONFIG)
    except Exception:
        log.exception("Download failed url=%s", url)
        return None

    if not downloaded:
        log.warning("Empty download url=%s", url)
        return None

    try:
        content = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
            config=_TRAFILATURA_CONFIG,
        )
    except Exception:
        log.exception("Extraction failed url=%s", url)
        return None

    if not content or len(content) < MIN_CONTENT_LENGTH:
        log.warning("Content too short url=%s len=%s", url, len(content) if content else 0)
        return None

    metadata = trafilatura.extract_metadata(downloaded)
    title = getattr(metadata, "title", None) if metadata else None
    published_at = _parse_iso_date(getattr(metadata, "date", None) if metadata else None)
    detected_source = getattr(metadata, "sitename", None) if metadata else None

    return {
        "url": url,
        "title": title,
        "content": content,
        "published_at": published_at,
        "source": source or detected_source,
    }
