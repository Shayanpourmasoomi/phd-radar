"""Text normalisation, term matching and date parsing."""
from __future__ import annotations

import datetime as dt
import re
import unicodedata

_EXTRA = str.maketrans({"ø": "o", "Ø": "O", "ł": "l", "Ł": "L", "đ": "d", "ß": "ss", "æ": "ae", "œ": "oe",
                        "’": "'", "‘": "'", "–": "-", "—": "-", " ": " "})


def norm(s: str | None) -> str:
    """Lower-case, strip accents, unify punctuation.  Used for ALL matching."""
    s = (s or "").translate(_EXTRA)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"\bph\.\s?d\b\.?", "phd", s)          # Ph.D. -> phd
    s = s.replace("*", "")                             # Mitarbeiter*in -> mitarbeiterin
    return re.sub(r"\s+", " ", s).strip()


_term_cache: dict[str, re.Pattern] = {}


def term_regex(term: str) -> re.Pattern:
    """'carbon pric*' -> regex.  '*' = any word ending; spaces/hyphens interchangeable.
    A '?' inside a term is kept as a regex optional char (e.g. 'decarboni?ation')."""
    if term in _term_cache:
        return _term_cache[term]
    t = norm(term.replace("*", "\x00")).replace("\x00", "*")
    wildcard_end = t.endswith("*")
    parts = [p for p in re.split(r"[\s\-]+", t) if p]
    pieces = []
    for p in parts:
        esc = re.escape(p.replace("*", "")).replace(r"\?", "?") if "?" in p else re.escape(p.replace("*", ""))
        if "*" in p:
            esc += r"\w*"
        pieces.append(esc)
    body = r"[\s\-]?".join(pieces)
    rx = re.compile(r"(?<![a-z0-9])" + body + ("" if wildcard_end else r"(?![a-z0-9])"))
    _term_cache[term] = rx
    return rx


def any_term(text: str, terms: list[str]) -> str | None:
    for t in terms:
        if term_regex(t).search(text):
            return t
    return None


# --------------------------------------------------------------------------- dates
_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _mon(s: str) -> int | None:
    return _MONTHS.get(s.strip(".").lower()[:3])


def _mk(y: int, m: int, d: int) -> dt.date | None:
    try:
        return dt.date(y, m, d)
    except ValueError:
        return None


def parse_date(s: str | None, today: dt.date | None = None) -> dt.date | None:
    """Parse the first date found in `s` (English month names, ISO, dd/mm/yyyy)."""
    if not s:
        return None
    today = today or dt.date.today()
    s = s.strip()
    m = re.search(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)", s)      # also "2026-11-15T23:59:59+01:00"
    if m:
        return _mk(int(m[1]), int(m[2]), int(m[3]))
    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([A-Za-z]{3,9})\.?,?\s+(\d{4})\b", s)
    if m and _mon(m[2]):
        return _mk(int(m[3]), _mon(m[2]), int(m[1]))
    m = re.search(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", s)
    if m and _mon(m[1]):
        return _mk(int(m[3]), _mon(m[1]), int(m[2]))
    m = re.search(r"\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b", s)
    if m:
        return _mk(int(m[3]), int(m[2]), int(m[1]))
    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\b", s)          # "31 Oct" (no year)
    if m and _mon(m[2]):
        for y in (today.year, today.year + 1):
            d = _mk(y, _mon(m[2]), int(m[1]))
            if d and d >= today - dt.timedelta(days=45):
                return d
    m = re.search(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b(?!\s*,?\s*\d{4})", s)   # "Oct 31"
    if m and _mon(m[1]):
        for y in (today.year, today.year + 1):
            d = _mk(y, _mon(m[1]), int(m[2]))
            if d and d >= today - dt.timedelta(days=45):
                return d
    return None


_DEADLINE_KEYS = re.compile(
    r"(application deadline|deadline|closing date|closes|close on|apply by|applications? (?:must|should) be (?:received|submitted) by|"
    r"applications? (?:are )?(?:accepted|welcome) until|review of applications? (?:begins|will begin) on|bewerbungsfrist|frist|"
    r"date limite|scadenza|fecha limite|solicitud hasta|until)\s*[:\-]?\s*", re.I)


def find_deadline(text: str | None, today: dt.date | None = None) -> tuple[dt.date | None, bool]:
    """-> (deadline date or None, rolling?)"""
    if not text:
        return None, False
    rolling = bool(re.search(r"\brolling\b|until (?:the )?(?:position|post) is filled|until filled", text, re.I))
    for m in _DEADLINE_KEYS.finditer(text):
        d = parse_date(text[m.end(): m.end() + 70], today)
        if d:
            return d, rolling
    return None, rolling


def ago_to_date(s: str, today: dt.date) -> dt.date | None:
    """'2 weeks ago' -> date."""
    m = re.search(r"(\d+|a|an|one)\s+(minute|hour|day|week|month|year)s?\s+ago", s, re.I)
    if not m:
        return None
    n = 1 if m[1].lower() in ("a", "an", "one") else int(m[1])
    unit = m[2].lower()
    days = {"minute": 0, "hour": 0, "day": 1, "week": 7, "month": 30, "year": 365}[unit] * n
    return today - dt.timedelta(days=days)
