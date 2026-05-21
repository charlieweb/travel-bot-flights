"""Known airline names — only these are accepted as carrier titles."""

from __future__ import annotations

import re

__all__ = (
    "KNOWN_AIRLINE_NAMES",
    "find_airline_in_text",
    "match_airline_from_operated_by",
    "match_airline_name",
)

# Longest names first so substring matching prefers full names.
KNOWN_AIRLINE_NAMES: tuple[str, ...] = (
    "American Airlines",
    "United Airlines",
    "Southwest Airlines",
    "Copa Airlines",
    "JetBlue Airways",
    "Alaska Airlines",
    "Frontier Airlines",
    "Spirit Airlines",
    "Singapore Airlines",
    "Turkish Airlines",
    "Qatar Airways",
    "Etihad Airways",
    "Virgin Atlantic",
    "Virgin Australia",
    "Air New Zealand",
    "All Nippon Airways",
    "China Eastern",
    "China Southern",
    "China Airlines",
    "Cathay Pacific",
    "LATAM Airlines",
    "British Airways",
    "Air Canada",
    "Air France",
    "Japan Airlines",
    "Korean Air",
    "TAP Air Portugal",
    "Sun Country",
    "Viva Aerobus",
    "Aeromexico",
    "Hawaiian",
    "Allegiant",
    "Lufthansa",
    "Avianca",
    "Emirates",
    "Iberia",
    "JetBlue",
    "Southwest",
    "WestJet",
    "Qantas",
    "Finnair",
    "Volaris",
    "SWISS",
    "KLM",
    "Delta",
    "United",
    "American",
    "Frontier",
    "Spirit",
    "Alaska",
    "Copa",
)

_OPERATED_BY_RE = re.compile(
    r"(?:operated by|Operado por)\s+([^\n|•]+)",
    re.IGNORECASE,
)


def match_airline_from_operated_by(text: str) -> str | None:
    """Match a known airline from an 'operated by …' phrase in card text."""
    match = _OPERATED_BY_RE.search(text)
    if not match:
        return None
    return match_airline_name(match.group(1))


def _canonical(name: str) -> str:
    return name.replace("COPA", "Copa")


def match_airline_name(text: str) -> str | None:
    """Return a known airline name if text is or contains one, else None."""
    stripped = (text or "").strip()
    if not stripped or len(stripped) > 80:
        return None
    lower = stripped.lower()
    for known in KNOWN_AIRLINE_NAMES:
        if lower == known.lower():
            return _canonical(known)
    upper = stripped.upper()
    for known in KNOWN_AIRLINE_NAMES:
        if known.upper() in upper:
            return _canonical(known)
    return None


def find_airline_in_text(text: str) -> str | None:
    """Return the longest known airline name found in text (names ordered longest-first)."""
    if not text.strip():
        return None
    upper = text.upper()
    for known in KNOWN_AIRLINE_NAMES:
        if known.upper() in upper:
            return _canonical(known)
    return None
