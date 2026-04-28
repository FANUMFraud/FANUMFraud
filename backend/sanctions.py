"""
Sanctions checking service using OpenSanctions/Yente search.

The important compliance distinction is:
- listed: checked and matched sanctions/watchlist data
- clear: checked and no relevant match found
- unavailable: check could not be performed
"""

from __future__ import annotations

import logging
import os
from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover - dependency guard for local dev
    requests = None  # type: ignore[assignment]

log = logging.getLogger(__name__)

OPENSANCTIONS_SEARCH_URL = "https://api.opensanctions.org/search/default"
OPENSANCTIONS_API_KEY = os.getenv("OPENSANCTIONS_API_KEY", "").strip()

DEMO_SANCTIONED_NIPS = {
    "1010000002": {
        "name": "FANUM Demo Sanctions Watchlist",
        "country": "International",
        "match_score": 0.94,
        "entity_id": "demo-vistula-logistics",
        "reason": "Demo sanctions hit for presentation flow",
    }
}

_SANCTIONS_CACHE: dict[str, dict[str, Any]] = {}


def check_sanctions(company_name: str, nip: str | None = None) -> dict[str, Any]:
    """Check if a company is present on sanctions/watchlist data."""
    search_term = company_name.strip().lower()
    cache_key = f"{search_term}_{nip or 'no_nip'}"
    if cache_key in _SANCTIONS_CACHE:
        return _SANCTIONS_CACHE[cache_key]

    if nip in DEMO_SANCTIONED_NIPS:
        result = _listed_result([DEMO_SANCTIONED_NIPS[nip]], "demo_sanctions")
        _SANCTIONS_CACHE[cache_key] = result
        return result

    if requests is None:
        result = _unavailable_result("requests_missing", "requests library not available")
        _SANCTIONS_CACHE[cache_key] = result
        return result

    if not search_term:
        result = _unavailable_result("empty_query", "empty company name")
        _SANCTIONS_CACHE[cache_key] = result
        return result

    if not OPENSANCTIONS_API_KEY:
        result = _unavailable_result("missing_api_key", "OPENSANCTIONS_API_KEY is not configured")
        _SANCTIONS_CACHE[cache_key] = result
        return result

    try:
        result = _query_opensanctions(search_term)
    except Exception as exc:
        log.warning("Sanctions check failed for '%s': %s", company_name, exc)
        result = _unavailable_result("api_error", str(exc))

    _SANCTIONS_CACHE[cache_key] = result
    return result


def _query_opensanctions(company_name: str) -> dict[str, Any]:
    params = {
        "q": company_name,
        "limit": 5,
        "schema": "Company",
    }
    headers = {
        "Authorization": f"ApiKey {OPENSANCTIONS_API_KEY}",
        "User-Agent": "FANUMFraud/0.1",
    }

    response = requests.get(
        OPENSANCTIONS_SEARCH_URL,
        params=params,
        headers=headers,
        timeout=8,
    )
    response.raise_for_status()

    data = response.json()
    results = data.get("results", [])
    if not results:
        return _clear_result("opensanctions")

    lists_found: list[dict[str, Any]] = []
    max_confidence = 0.0
    for entity in results[:5]:
        match_score = _calculate_match_score(entity, company_name)
        is_target = bool(entity.get("target"))
        if is_target and match_score >= 0.55:
            lists_found.append(
                {
                    "name": _entity_dataset_label(entity),
                    "country": _entity_country(entity),
                    "match_score": round(match_score, 2),
                    "entity_id": entity.get("id"),
                    "caption": entity.get("caption"),
                }
            )
            max_confidence = max(max_confidence, match_score)

    if not lists_found:
        return _clear_result("opensanctions")

    return {
        "is_sanctioned": True,
        "status": "listed",
        "available": True,
        "lists": lists_found,
        "confidence": round(max_confidence, 2),
        "source": "opensanctions",
    }


def _listed_result(lists: list[dict[str, Any]], source: str) -> dict[str, Any]:
    confidence = max((float(item.get("match_score", 0.0)) for item in lists), default=0.0)
    return {
        "is_sanctioned": True,
        "status": "listed",
        "available": True,
        "lists": lists,
        "confidence": round(confidence, 2),
        "source": source,
    }


def _clear_result(source: str) -> dict[str, Any]:
    return {
        "is_sanctioned": False,
        "status": "clear",
        "available": True,
        "lists": [],
        "confidence": 0.0,
        "source": source,
    }


def _unavailable_result(source: str, reason: str) -> dict[str, Any]:
    return {
        "is_sanctioned": False,
        "status": "unavailable",
        "available": False,
        "lists": [],
        "confidence": 0.0,
        "source": source,
        "reason": reason,
    }


def _calculate_match_score(entity: dict[str, Any], company_name: str) -> float:
    entity_caption = str(entity.get("caption", "")).lower()
    company_lower = company_name.lower()

    api_score = float(entity.get("score") or 0.0)
    if api_score > 1.0:
        api_score = api_score / 100.0

    if entity_caption == company_lower:
        return max(api_score, 0.95)
    if company_lower in entity_caption or entity_caption in company_lower:
        return max(api_score, 0.80)

    entity_tokens = set(entity_caption.split())
    company_tokens = set(company_lower.split())
    overlap = len(entity_tokens & company_tokens)
    max_tokens = max(len(entity_tokens), len(company_tokens))
    token_score = min(0.75, overlap / max_tokens) if max_tokens else 0.0
    return max(api_score, token_score)


def _entity_country(entity: dict[str, Any]) -> str:
    countries = entity.get("countries") or entity.get("properties", {}).get("country") or []
    if isinstance(countries, list) and countries:
        return str(countries[0]).upper()
    return "International"


def _entity_dataset_label(entity: dict[str, Any]) -> str:
    datasets = entity.get("datasets") or []
    if isinstance(datasets, list) and datasets:
        return str(datasets[0])
    return str(entity.get("caption") or "OpenSanctions match")


__all__ = ["check_sanctions"]
