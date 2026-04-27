"""
Sanctions checking service using OpenSanctions API.

Checks if a company is on any sanctions list (OFAC, EU, UN, etc.)
"""

import logging
from typing import Any

try:
    import requests
except ImportError:
    requests = None  # type: ignore

log = logging.getLogger(__name__)

OPENSANCTIONS_API_URL = "https://api.opensanctions.org/datasets"
OPENSANCTIONS_ENTITIES_URL = "https://api.opensanctions.org/entities"

# Cache for sanctions lists (in production, use Redis)
_SANCTIONS_CACHE: dict[str, dict[str, Any]] = {}


def check_sanctions(company_name: str, nip: str | None = None) -> dict[str, Any]:
    """
    Check if company is on any sanctions list.

    Returns:
        {
            "is_sanctioned": bool,
            "lists": [{"name": str, "country": str, "match_score": float}],
            "confidence": float,
            "source": str,
        }
    """
    if requests is None:
        log.warning("requests library not available, skipping sanctions check")
        return {
            "is_sanctioned": False,
            "lists": [],
            "confidence": 0.0,
            "source": "unavailable",
        }

    # Normalize search terms
    search_term = company_name.strip().lower()
    if not search_term:
        return {
            "is_sanctioned": False,
            "lists": [],
            "confidence": 0.0,
            "source": "empty",
        }

    # Check cache first
    cache_key = f"{search_term}_{nip or 'no_nip'}"
    if cache_key in _SANCTIONS_CACHE:
        return _SANCTIONS_CACHE[cache_key]

    try:
        result = _query_opensanctions(search_term, nip)
        _SANCTIONS_CACHE[cache_key] = result
        return result
    except Exception as e:
        log.warning(f"Sanctions check failed for '{company_name}': {e}")
        return {
            "is_sanctioned": False,
            "lists": [],
            "confidence": 0.0,
            "source": "error",
        }


def _query_opensanctions(company_name: str, nip: str | None = None) -> dict[str, Any]:
    """Query OpenSanctions API for company matches."""
    try:
        # Search for entity by name
        params = {
            "q": company_name,
            "dataset": "all",
        }

        response = requests.get(
            OPENSANCTIONS_ENTITIES_URL,
            params=params,
            timeout=5,
        )
        response.raise_for_status()

        data = response.json()
        results = data.get("results", [])

        if not results:
            return {
                "is_sanctioned": False,
                "lists": [],
                "confidence": 0.0,
                "source": "opensanctions",
            }

        # Process matches
        lists_found = []
        max_confidence = 0.0

        for entity in results[:5]:  # Top 5 matches
            # Calculate match score based on schema/properties
            match_score = _calculate_match_score(entity, company_name)

            if match_score > 0.5:  # Threshold
                sanctions_list = entity.get("caption", "").lower()
                country = entity.get("countries", [None])[0]

                lists_found.append(
                    {
                        "name": entity.get("caption", "Unknown List"),
                        "country": country or "International",
                        "match_score": round(match_score, 2),
                        "entity_id": entity.get("id"),
                    }
                )
                max_confidence = max(max_confidence, match_score)

        is_sanctioned = len(lists_found) > 0 and max_confidence > 0.6

        return {
            "is_sanctioned": is_sanctioned,
            "lists": lists_found,
            "confidence": round(max_confidence, 2),
            "source": "opensanctions",
        }

    except requests.RequestException as e:
        log.warning(f"OpenSanctions API error: {e}")
        return {
            "is_sanctioned": False,
            "lists": [],
            "confidence": 0.0,
            "source": "api_error",
        }


def _calculate_match_score(entity: dict[str, Any], company_name: str) -> float:
    """
    Calculate match score between entity and company name.

    Simple heuristic:
    - Exact match or caption contains name: 0.95
    - Name contains entity: 0.80
    - Fuzzy match: 0.60
    """
    entity_caption = entity.get("caption", "").lower()
    company_lower = company_name.lower()

    if entity_caption == company_lower:
        return 0.95

    if company_lower in entity_caption or entity_caption in company_lower:
        return 0.80

    # Simple token overlap for fuzzy matching
    entity_tokens = set(entity_caption.split())
    company_tokens = set(company_lower.split())
    overlap = len(entity_tokens & company_tokens)
    max_tokens = max(len(entity_tokens), len(company_tokens))

    if max_tokens > 0:
        return min(0.75, overlap / max_tokens)

    return 0.0


__all__ = ["check_sanctions", "SanctionsCheck"]
