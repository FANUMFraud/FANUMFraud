from __future__ import annotations

import re

NIP_WEIGHTS = (6, 5, 7, 2, 3, 4, 5, 6, 7)


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


def nip_check(nip: str | None) -> dict[str, str | bool | None]:
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


__all__ = ["normalize_nip", "validate_nip", "nip_check"]
