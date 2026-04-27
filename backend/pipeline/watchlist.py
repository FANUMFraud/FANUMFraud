from __future__ import annotations

import json
import logging
import os
import re
from contextlib import contextmanager
from dataclasses import dataclass
from urllib.parse import quote_plus

from sqlalchemy.orm import Session

from database import SessionLocal
from elastic import index_company
from models import Company

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class WatchlistCompany:
    name: str
    aliases: tuple[str, ...]


WATCHLIST_COMPANIES: tuple[WatchlistCompany, ...] = (
    WatchlistCompany(
        name="InPost",
        aliases=("InPost", "InPost S.A.", "Integer.pl", "Paczkomaty"),
    ),
    WatchlistCompany(
        name="ORLEN",
        aliases=("ORLEN", "PKN ORLEN", "ORLEN S.A.", "Polski Koncern Naftowy"),
    ),
    WatchlistCompany(
        name="zondacrypto",
        aliases=("zondacrypto", "zonda", "zonda crypto", "BitBay"),
    ),
    WatchlistCompany(
        name="Żabka",
        aliases=("Żabka", "Zabka", "Zabka Polska", "Żabka Polska"),
    ),
    WatchlistCompany(
        name="Nestle",
        aliases=("Nestle", "Nestlé", "Nestle Polska", "Nestlé Polska"),
    ),
    WatchlistCompany(
        name="Allegro",
        aliases=("Allegro", "Allegro.eu", "Allegro.eu S.A."),
    ),
    WatchlistCompany(
        name="PKO Bank Polski",
        aliases=("PKO BP", "PKO Bank Polski", "PKOBP"),
    ),
    WatchlistCompany(
        name="CD Projekt",
        aliases=("CD Projekt", "CDPROJEKT", "CDR"),
    ),
    WatchlistCompany(
        name="PZU",
        aliases=("PZU", "PZU S.A.", "Powszechny Zaklad Ubezpieczen"),
    ),
    WatchlistCompany(
        name="LPP",
        aliases=("LPP", "LPP S.A.", "Reserved", "Sinsay", "Cropp", "House"),
    ),
)

RISK_QUERY_TERMS: tuple[str, ...] = (
    "łapówka",
    "zarzuty",
    "korupcja",
    "sankcje",
    "pranie pieniędzy",
    "oszustwo",
    "wyłudzenie",
    "prokuratura",
    "UOKiK",
    "KNF",
    "postępowanie",
)

WATCHLIST_FEED_WINDOW = os.getenv("WATCHLIST_FEED_WINDOW", "when:30d")


@contextmanager
def _session() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_watchlist_companies() -> dict[str, int]:
    stats = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}

    with _session() as db:
        companies = db.query(Company).all()
        lookup: dict[str, Company] = {
            _normalize_key(company.name): company
            for company in companies
            if _normalize_key(company.name)
        }
        touched: list[Company] = []

        for entry in WATCHLIST_COMPANIES:
            try:
                company = lookup.get(_normalize_key(entry.name))
                if company is None:
                    company = Company(
                        name=entry.name,
                        aliases=json.dumps(list(entry.aliases), ensure_ascii=False),
                        current_score=100.0,
                    )
                    db.add(company)
                    _mark_touched(touched, company)
                    stats["created"] += 1
                else:
                    current_aliases = _load_aliases(company.aliases)
                    merged_aliases = _merge_aliases(
                        current_aliases, list(entry.aliases)
                    )
                    if merged_aliases != current_aliases:
                        company.aliases = json.dumps(merged_aliases, ensure_ascii=False)
                        _mark_touched(touched, company)
                        stats["updated"] += 1
                    else:
                        stats["skipped"] += 1

                lookup[_normalize_key(entry.name)] = company
            except Exception:
                stats["errors"] += 1
                log.exception("Failed to upsert watchlist company name=%s", entry.name)

        try:
            db.commit()
        except Exception:
            db.rollback()
            stats["errors"] += 1
            log.exception("Failed to commit watchlist bootstrap")
            return stats

        for company in touched:
            try:
                index_company(company)
            except Exception:
                log.warning(
                    "Failed to index watchlist company id=%s", company.id, exc_info=True
                )

    return stats


def watchlist_rss_feeds() -> dict[str, str]:
    feeds: dict[str, str] = {}
    risk_clause = " OR ".join(f'"{term}"' for term in RISK_QUERY_TERMS)
    for item in WATCHLIST_COMPANIES:
        company_term = item.name
        query = f'"{company_term}" ({risk_clause}) {WATCHLIST_FEED_WINDOW}'.strip()
        encoded_query = quote_plus(query)
        feeds[f"watchlist:{item.name.lower()}"] = (
            f"https://news.google.com/rss/search?q={encoded_query}&hl=pl&gl=PL&ceid=PL:pl"
        )
    return feeds


def _load_aliases(raw_aliases: str | list[str] | None) -> list[str]:
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


def _merge_aliases(existing: list[str], incoming: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in [*existing, *incoming]:
        clean = str(value).strip()
        if not clean:
            continue
        normalized = _normalize_key(clean)
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(clean)
    return result


def _mark_touched(touched: list[Company], company: Company) -> None:
    if all(item is not company for item in touched):
        touched.append(company)


def _normalize_key(value: str | None) -> str:
    if value is None:
        return ""
    lowered = str(value).strip().lower()
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered
