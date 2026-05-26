"""
Marketplace policy compliance sanitizer.

Replaces terms that trigger automated policy violations on Wallapop and
similar marketplaces. Focused on TV/TDT ecosystem terms (satellite,
decoder, IPTV) and other restricted categories (spy cameras, exam
earpieces, unlocked phones).

Rules are ordered: longer phrases first to avoid partial matches.
For example, "receptor satélite" → "sintonizador TDT" runs before
"satélite" → "TDT" to avoid incorrect replacements.
"""
from __future__ import annotations

import re
from typing import Optional

_RULES: list[tuple[re.Pattern[str], str]] = [
    # TV/TDT ecosystem — longer phrases first to avoid partial matches
    (re.compile(r"receptor\s+sat[eé]lite", re.IGNORECASE), "sintonizador TDT"),
    (re.compile(r"decodificador(?:es)?", re.IGNORECASE), "sintonizador"),
    (re.compile(r"\bsat[eé]lite\b", re.IGNORECASE), "TDT"),
    (re.compile(r"\biptv\b", re.IGNORECASE), "televisión"),
    (re.compile(r"\bkodi\b", re.IGNORECASE), ""),
    (re.compile(r"\bjailbreak\b", re.IGNORECASE), ""),
    (re.compile(r"\bcardsharing\b", re.IGNORECASE), ""),
    (re.compile(r"\bdvb-s\b", re.IGNORECASE), "DVB-T2"),
    (re.compile(r"\bandroid\s*tv\b", re.IGNORECASE), "Smart TV"),
    (re.compile(r"\btv\s*box\b", re.IGNORECASE), "reproductor"),
    (re.compile(r"\bemulador(?:es)?\b", re.IGNORECASE), "software juegos"),
    (re.compile(r"\btester\b", re.IGNORECASE), "comprobador"),
    (re.compile(r"\blingote\b", re.IGNORECASE), "pieza"),
    (re.compile(r"\bhack(?:eado|er)?\b", re.IGNORECASE), ""),
    (re.compile(r"\bpiratead[oa]\b", re.IGNORECASE), ""),
    # Exam earpieces — progressive specificity
    (re.compile(
        r"\bpinganillo(?:s)?\s+(?:bluetooth\s+)?(?:mini\s+)?invisible\s+para\s+examen",
        re.IGNORECASE,
    ), "auricular bluetooth mini"),
    (re.compile(r"\bpinganillo(?:s)?\s+para\s+examen", re.IGNORECASE), "auricular bluetooth"),
    (re.compile(r"\bpinganillo(?:s)?", re.IGNORECASE), "auricular bluetooth"),
    # Spy cameras — compound phrases before isolated words
    (re.compile(r"\bc[aá]mara\s+oculta", re.IGNORECASE), "cámara compacta"),
    (re.compile(r"\bc[aá]mara\s+esp[ií]a", re.IGNORECASE), "cámara mini"),
    (re.compile(r"\breloj\s+esp[ií]a", re.IGNORECASE), "reloj cámara"),
    (re.compile(r"\besp[ií]a\b", re.IGNORECASE), ""),
    (re.compile(r"\boculta\b", re.IGNORECASE), "compacta"),
    # Unlocked phones
    (re.compile(r"\bdesbloquead[oa]\b", re.IGNORECASE), "libre"),
    # GPS trackers
    (re.compile(r"\blocalizador\s+gps\s+coche", re.IGNORECASE), "tracker GPS vehículo"),
    (re.compile(r"\bgps\s+coche\s+bater[ií]a", re.IGNORECASE), "GPS vehículo batería"),
    # Gas bottles
    (re.compile(r"\bbombona\s+(?:gpl|gas)\b", re.IGNORECASE), "bombona"),
    (re.compile(r"\bjailbreak(?:ed)?\b", re.IGNORECASE), ""),
]

_TITLE_MAX = 50


def _sanitize_core(text: str) -> str:
    """Apply all replacement rules and collapse resulting double spaces."""
    out = str(text).strip()
    for pattern, repl in _RULES:
        out = pattern.sub(repl, out)
    return re.sub(r"\s{2,}", " ", out).strip()


def sanitize_text(text: Optional[str], *, for_title: bool = False) -> str:
    """
    Sanitize text for marketplace policy compliance.

    Args:
        text: Input text to clean.
        for_title: If True, truncate to 50 chars at last complete word boundary.

    Returns:
        Cleaned text, or empty string if input is None/empty/"nan"/"none".
    """
    if not text:
        return ""
    out = str(text).strip()
    if not out or out.lower() in ("nan", "none"):
        return ""
    out = _sanitize_core(out)
    if for_title and len(out) > _TITLE_MAX:
        cut = out[:_TITLE_MAX].rstrip()
        if len(out) > _TITLE_MAX and not out[_TITLE_MAX].isspace():
            cut = cut.rsplit(" ", 1)[0]
        out = cut
    return out


def text_needs_sanitizing(text: Optional[str]) -> bool:
    """Check if the text contains any terms that would be replaced."""
    if not text:
        return False
    return _sanitize_core(str(text).strip()) != str(text).strip()


def has_risk_word(*texts: Optional[str]) -> bool:
    """True if ANY of the provided texts contains a flagged term."""
    for t in texts:
        if t and text_needs_sanitizing(t):
            return True
    return False
