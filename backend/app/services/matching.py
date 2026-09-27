from __future__ import annotations

import re


ABBREVIATIONS = {
    "STREET": "ST",
    "AVENUE": "AVE",
    "BOULEVARD": "BLVD",
    "PLACE": "PL",
    "ROAD": "RD",
    "DRIVE": "DR",
    "LANE": "LN",
    "COURT": "CT",
}


def normalize_address(value: str) -> str:
    text = re.sub(r"\b(APT|UNIT|#)\s*[A-Z0-9-]+\b", "", value.upper())
    text = re.sub(r"[^A-Z0-9-]+", " ", text).strip()
    words = [ABBREVIATIONS.get(word, word) for word in text.split()]
    return " ".join(words)


def same_building_address(candidate: str | None, selected: str) -> bool:
    if not candidate:
        return False
    return normalize_address(candidate) == normalize_address(selected)


def build_bbl(borough_code: str, block: str, lot: str) -> str:
    return f"{borough_code}{int(block):05d}{int(lot):04d}"
