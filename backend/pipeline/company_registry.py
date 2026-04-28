from __future__ import annotations

import json
import logging
import os
import re
from contextlib import contextmanager
from dataclasses import dataclass

import httpx
from sqlalchemy.orm import Session

from database import SessionLocal
from elastic import index_company
from models import Company

log = logging.getLogger(__name__)

GLEIF_LEI_RECORDS_URL = os.getenv(
    "COMPANY_REGISTRY_URL",
    "https://api.gleif.org/api/v1/lei-records",
)
COMPANY_REGISTRY_COUNTRY = os.getenv("COMPANY_REGISTRY_COUNTRY", "PL")
COMPANY_REGISTRY_CATEGORY = os.getenv("COMPANY_REGISTRY_CATEGORY", "GENERAL")
DEFAULT_COMPANY_SYNC_LIMIT = int(os.getenv("COMPANY_SYNC_LIMIT", "300"))
DEFAULT_PAGE_SIZE = int(os.getenv("COMPANY_REGISTRY_PAGE_SIZE", "100"))
HTTP_TIMEOUT_SECONDS = float(os.getenv("COMPANY_REGISTRY_TIMEOUT_SECONDS", "20"))

LEGAL_SUFFIX_PATTERN = re.compile(
    r"\b("
    r"sp[oó]łka\s+akcyjna"
    r"|s\.?\s*a\.?"
    r"|sp[oó]łka\s+z\s+ograniczon[aą]\s+odpowiedzialno[sś]ci[aą]"
    r"|sp\.?\s*z\s*o\.?\s*o\.?"
    r"|public\s+limited"
    r"|limited"
    r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RegistryCompany:
    name: str
    lei_tag: str
    aliases: list[str]


@contextmanager
def _session() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def sync_companies_from_registry(limit: int | None = None) -> dict[str, int]:
    max_records = limit if limit is not None else DEFAULT_COMPANY_SYNC_LIMIT
    stats = {"fetched": 0, "created": 0, "updated": 0, "skipped": 0, "errors": 0}

    if max_records <= 0:
        return stats

    with _session() as db:
        existing_companies = db.query(Company).all()
        by_name: dict[str, Company] = {}
        by_lei_tag: dict[str, Company] = {}
        for company in existing_companies:
            _index_company_lookups(company, by_name, by_lei_tag)

        touched: list[Company] = []

        try:
            for raw_record in _iter_registry_records(max_records=max_records):
                stats["fetched"] += 1

                registry_company = _record_to_registry_company(raw_record)
                if registry_company is None:
                    stats["skipped"] += 1
                    continue

                try:
                    company = by_lei_tag.get(registry_company.lei_tag)
                    if company is None:
                        company = by_name.get(_normalize_key(registry_company.name))

                    if company is None:
                        company = Company(
                            name=registry_company.name,
                            current_score=100.0,
                            aliases=json.dumps(
                                registry_company.aliases, ensure_ascii=False
                            ),
                        )
                        db.add(company)
                        stats["created"] += 1
                        _mark_touched(touched, company)
                    else:
                        existing_aliases = _load_aliases(company.aliases)
                        merged_aliases = _merge_aliases(
                            existing_aliases, registry_company.aliases
                        )
                        if merged_aliases != existing_aliases:
                            company.aliases = json.dumps(
                                merged_aliases, ensure_ascii=False
                            )
                            stats["updated"] += 1
                            _mark_touched(touched, company)
                        else:
                            stats["skipped"] += 1

                    _index_company_lookups(company, by_name, by_lei_tag)
                except Exception:
                    stats["errors"] += 1
                    log.exception(
                        "Failed to upsert registry company name=%s",
                        registry_company.name,
                    )
        except Exception:
            stats["errors"] += 1
            log.exception("Failed to fetch online company registry")

        try:
            db.commit()
        except Exception:
            db.rollback()
            stats["errors"] += 1
            log.exception("Failed to commit online company registry sync")
            return stats

        for company in touched:
            try:
                index_company(company)
            except Exception:
                log.warning(
                    "Failed to index synced company id=%s", company.id, exc_info=True
                )

    log.info("Company registry sync done: %s", stats)
    return stats


def _iter_registry_records(max_records: int):
    params = {
        "filter[entity.legalAddress.country]": COMPANY_REGISTRY_COUNTRY,
        "filter[entity.status]": "ACTIVE",
        "page[size]": str(DEFAULT_PAGE_SIZE),
    }
    if COMPANY_REGISTRY_CATEGORY:
        params["filter[entity.category]"] = COMPANY_REGISTRY_CATEGORY

    next_url = GLEIF_LEI_RECORDS_URL
    fetched = 0

    with httpx.Client(
        timeout=HTTP_TIMEOUT_SECONDS,
        headers={"User-Agent": "FanumFraud/1.0"},
        follow_redirects=True,
    ) as client:
        while next_url and fetched < max_records:
            response = client.get(next_url, params=params)
            response.raise_for_status()
            payload = response.json()

            records = payload.get("data") or []
            if not records:
                break

            for record in records:
                yield record
                fetched += 1
                if fetched >= max_records:
                    break

            next_url = (payload.get("links") or {}).get("next")
            params = None


def _record_to_registry_company(record: dict) -> RegistryCompany | None:
    attributes = record.get("attributes") or {}
    entity = attributes.get("entity") or {}
    legal_name = str((entity.get("legalName") or {}).get("name") or "").strip()
    lei = str(record.get("id") or "").strip().upper()

    if not legal_name or not lei:
        return None

    aliases: list[str] = []

    for item in entity.get("otherNames") or []:
        alias = _extract_name(item)
        if alias:
            aliases.append(alias)

    for item in entity.get("transliteratedOtherNames") or []:
        alias = _extract_name(item)
        if alias:
            aliases.append(alias)

    short_name = _strip_legal_suffix(legal_name)
    if short_name:
        aliases.append(short_name)

    registered_as = str(entity.get("registeredAs") or "").strip()
    if registered_as:
        aliases.append(f"REG:{registered_as}")

    lei_tag = f"LEI:{lei}"
    aliases.append(lei_tag)

    deduped_aliases = _dedupe_preserve_order(aliases)

    return RegistryCompany(name=legal_name, lei_tag=lei_tag, aliases=deduped_aliases)


def _strip_legal_suffix(name: str) -> str | None:
    stripped = LEGAL_SUFFIX_PATTERN.sub(" ", name)
    stripped = re.sub(r"\s+", " ", stripped).strip(" ,.-")
    if len(stripped) < 4:
        return None
    if _normalize_key(stripped) == _normalize_key(name):
        return None
    return stripped


def _index_company_lookups(
    company: Company,
    by_name: dict[str, Company],
    by_lei_tag: dict[str, Company],
) -> None:
    name_key = _normalize_key(company.name)
    if name_key and name_key not in by_name:
        by_name[name_key] = company

    aliases = _load_aliases(company.aliases)
    for alias in aliases:
        normalized_alias = _normalize_key(alias)
        if normalized_alias and normalized_alias not in by_name:
            by_name[normalized_alias] = company

        upper_alias = alias.upper().strip()
        if upper_alias.startswith("LEI:") and upper_alias not in by_lei_tag:
            by_lei_tag[upper_alias] = company


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
    return _dedupe_preserve_order([*existing, *incoming])


def _extract_name(raw_value) -> str:
    if isinstance(raw_value, dict):
        return str(raw_value.get("name") or "").strip()
    return str(raw_value or "").strip()


def _mark_touched(touched: list[Company], company: Company) -> None:
    if all(existing is not company for existing in touched):
        touched.append(company)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = str(value).strip()
        if not clean:
            continue
        key = _normalize_key(clean)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(clean)
    return result


def _normalize_key(value: str | None) -> str:
    if value is None:
        return ""
    normalized = str(value).strip().lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    sync_companies_from_registry()
