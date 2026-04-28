from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

NIP_WEIGHTS = (6, 5, 7, 2, 3, 4, 5, 6, 7)
MF_VAT_REGISTRY_URL = "https://wl-api.mf.gov.pl/api/search/nip/{nip}"
REGISTRY_TIMEOUT_SECONDS = float(os.getenv("NIP_REGISTRY_TIMEOUT", "5.0"))
REGISTRY_CACHE_TTL_HOURS = float(os.getenv("NIP_REGISTRY_CACHE_HOURS", "24"))

log = logging.getLogger(__name__)


def normalize_nip(nip: str | None) -> str | None:
    digits = re.sub(r"\D+", "", str(nip or ""))
    return digits or None


def validate_nip(nip: str | None) -> bool:
    normalized = normalize_nip(nip)
    if normalized is None or len(normalized) != 10:
        return False

    digits = [int(char) for char in normalized]
    checksum = sum(weight * digit for weight, digit in zip(NIP_WEIGHTS, digits[:9])) % 11
    return checksum != 10 and checksum == digits[9]


def nip_check(nip: str | None) -> dict[str, Any]:
    """Pure checksum / format validation. No registry lookup."""
    normalized = normalize_nip(nip)
    if normalized is None:
        return {
            "status": "missing",
            "valid": False,
            "normalized": None,
            "reason": "NIP is missing",
        }
    if len(normalized) != 10:
        return {
            "status": "invalid",
            "valid": False,
            "normalized": normalized,
            "reason": "NIP must contain exactly 10 digits",
        }
    if not validate_nip(normalized):
        return {
            "status": "invalid",
            "valid": False,
            "normalized": normalized,
            "reason": "NIP checksum is invalid",
        }
    return {
        "status": "valid",
        "valid": True,
        "normalized": normalized,
        "reason": None,
    }


def fetch_nip_registry(nip: str) -> dict[str, Any]:
    """Look up a NIP in the public Polish MF VAT whitelist.

    Returns a dict with registry_status in {"verified", "not_found", "unavailable"},
    plus best-effort registry_name / registry_vat_status. Never raises.
    """
    normalized = normalize_nip(nip)
    if normalized is None or len(normalized) != 10 or not validate_nip(normalized):
        return _registry_unavailable("NIP is not a valid 10-digit Polish identifier")

    today = datetime.now(timezone.utc).date().isoformat()
    url = MF_VAT_REGISTRY_URL.format(nip=normalized)
    try:
        response = httpx.get(
            url,
            params={"date": today},
            timeout=REGISTRY_TIMEOUT_SECONDS,
            headers={"Accept": "application/json", "User-Agent": "FanumFraud/1.0"},
        )
    except httpx.RequestError as exc:
        log.warning("MF VAT registry request failed: %s", exc)
        return _registry_unavailable(f"MF VAT registry request failed: {exc}")

    if response.status_code == 404:
        return _registry_payload(
            status="not_found",
            reason="NIP not present in the MF VAT whitelist",
            checked_at=datetime.now(timezone.utc),
        )
    if response.status_code >= 400:
        return _registry_unavailable(
            f"MF VAT registry returned HTTP {response.status_code}"
        )

    try:
        payload = response.json()
    except ValueError:
        return _registry_unavailable("MF VAT registry returned non-JSON response")

    subject = (payload.get("result") or {}).get("subject")
    if not subject:
        return _registry_payload(
            status="not_found",
            reason="MF VAT registry has no subject for this NIP",
            checked_at=datetime.now(timezone.utc),
        )

    return _registry_payload(
        status="verified",
        name=subject.get("name"),
        vat_status=subject.get("statusVat"),
        reason=None,
        checked_at=datetime.now(timezone.utc),
    )


def ensure_nip_registry(
    db,
    company,
    *,
    ttl_hours: float | None = None,
    allow_remote: bool = True,
) -> dict[str, Any]:
    """Return cached registry data, refreshing from MF API when stale.

    The Company model carries the cache columns; this function updates and
    persists them when it performs a remote refresh.
    """
    ttl = float(ttl_hours if ttl_hours is not None else REGISTRY_CACHE_TTL_HOURS)
    cached = _company_registry_cache(company)
    if cached and not _cache_is_stale(cached.get("checked_at"), ttl):
        return cached

    if not allow_remote:
        return cached or _registry_payload(status="not_checked", reason=None)

    if company.nip is None:
        return _registry_payload(status="not_checked", reason="NIP is missing")

    fresh = fetch_nip_registry(company.nip)
    company.nip_registry_status = fresh.get("status")
    company.nip_registry_name = fresh.get("name")
    company.nip_registry_vat_status = fresh.get("vat_status")
    company.nip_registry_source = fresh.get("source")
    checked_at = fresh.get("checked_at")
    if isinstance(checked_at, datetime):
        company.nip_registry_checked_at = checked_at.replace(tzinfo=None)
    elif isinstance(checked_at, str):
        try:
            company.nip_registry_checked_at = datetime.fromisoformat(
                checked_at.replace("Z", "+00:00")
            ).astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError:
            company.nip_registry_checked_at = None
    else:
        company.nip_registry_checked_at = None
    company.nip_registry_reason = fresh.get("reason")
    try:
        db.add(company)
        db.commit()
    except Exception:  # pragma: no cover - persistence best-effort
        log.warning("Failed to persist NIP registry cache for company %s", getattr(company, "id", None))
        db.rollback()
    return fresh


def _company_registry_cache(company) -> dict[str, Any] | None:
    status = getattr(company, "nip_registry_status", None)
    if not status:
        return None
    checked_at = getattr(company, "nip_registry_checked_at", None)
    return {
        "status": status,
        "name": getattr(company, "nip_registry_name", None),
        "vat_status": getattr(company, "nip_registry_vat_status", None),
        "source": getattr(company, "nip_registry_source", None) or "mf-vat-whitelist",
        "checked_at": checked_at.isoformat() if isinstance(checked_at, datetime) else checked_at,
        "reason": getattr(company, "nip_registry_reason", None),
    }


def _cache_is_stale(checked_at_iso: Any, ttl_hours: float) -> bool:
    if not checked_at_iso:
        return True
    if isinstance(checked_at_iso, datetime):
        checked_at = checked_at_iso
    else:
        try:
            checked_at = datetime.fromisoformat(str(checked_at_iso).replace("Z", "+00:00"))
        except ValueError:
            return True
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - checked_at
    return age > timedelta(hours=ttl_hours)


def _registry_payload(
    *,
    status: str,
    name: str | None = None,
    vat_status: str | None = None,
    reason: str | None = None,
    source: str = "mf-vat-whitelist",
    checked_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "name": name,
        "vat_status": vat_status,
        "source": source,
        "checked_at": checked_at.isoformat() if checked_at else None,
        "reason": reason,
    }


def _registry_unavailable(reason: str) -> dict[str, Any]:
    return _registry_payload(
        status="unavailable",
        reason=reason,
        checked_at=datetime.now(timezone.utc),
    )


def merge_nip_check(
    checksum_check: dict[str, Any],
    registry: dict[str, Any] | None,
) -> dict[str, Any]:
    """Combine checksum result with registry cache into the NipCheck schema shape."""
    merged = dict(checksum_check)
    if registry:
        merged.update(
            {
                "registry_status": registry.get("status"),
                "registry_name": registry.get("name"),
                "registry_vat_status": registry.get("vat_status"),
                "registry_source": registry.get("source"),
                "registry_checked_at": registry.get("checked_at"),
                "registry_reason": registry.get("reason"),
            }
        )
    return merged


__all__ = [
    "normalize_nip",
    "validate_nip",
    "nip_check",
    "fetch_nip_registry",
    "ensure_nip_registry",
    "merge_nip_check",
]
