"""Pure-logic helpers for parsing episode numbers, titles and seasons from captions."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Tartib muhim: avval aniqroq namunalar.
_EPISODE_PATTERNS = [
    re.compile(r"\[(\d{1,4})\s*-?\s*(?:qism|seri[yj]a|episode|epizod|ep)\]", re.IGNORECASE),
    re.compile(r"(?:^|\s|#)(?:qism|seri[yj]a|episode|epizod|ep|e)\s*[.#_-]?\s*(\d{1,4})", re.IGNORECASE),
    re.compile(r"(\d{1,4})\s*(?:-?\s*)(?:qism|seri[yj]a|episode|epizod)", re.IGNORECASE),
    re.compile(r"[Ss](\d{1,3})[Ee](\d{1,4})"),
    re.compile(r"\bE(\d{2,4})\b"),
]

_SEASON_PATTERNS = [
    re.compile(r"(\d{1,2})\s*(?:-?\s*)(?:fasl|season|sezon)", re.IGNORECASE),
    re.compile(r"(?:fasl|season|sezon)\s*[.#_-]?\s*(\d{1,2})", re.IGNORECASE),
    re.compile(r"[Ss](\d{1,3})[Ee]\d{1,4}"),
]

_TITLE_EPISODE_RE = re.compile(
    r"^(?P<title>.+?)\s*[-—–|]?\s*"
    r"(?:\[?\s*(?:\d{1,4}\s*-?\s*)?(?:qism|seri[yj]a|episode|epizod|ep|e)\s*[.#_-]?\s*\d{0,4}\s*\]?"
    r"|\[?\s*\d{1,4}\s*-?\s*(?:qism|seri[yj]a|episode|epizod)\s*\]?)",
    re.IGNORECASE,
)

_STRIP_SUFFIXES = re.compile(
    r"(?:\s*[-—–|]?\s*(?:qism|seri[yj]a|episode|epizod|ep|e)\s*[.#_-]?\s*\d{1,4})"
    r"|(?:\s*\d{1,4}\s*-?\s*(?:qism|seri[yj]a|episode|epizod))"
    r"|(?:\s*\d{1,2}\s*-?\s*(?:fasl|season|sezon))"
    r"|(?:\s*(?:fasl|season|sezon)\s*[.#_-]?\s*\d{1,2})"
    r"|(?:\s*[Ss]\d{1,3}[Ee]\d{1,4})"
    r"|(?:\s*\bE\d{2,4}\b)",
    re.IGNORECASE,
)

_KANAL_LINE_RE = re.compile(r"^\s*(?:kanal|channel)\s*[:]\s*@", re.IGNORECASE)

_EMOJI_RE = re.compile(
    r"[\U0001F300-\U0001F9FF\U00002600-\U000027BF\U0000FE00-\U0000FE0F"
    r"\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002702-\U000027B0"
    r"\U0000200D\U0000FE0F]+",
)


@dataclass(frozen=True)
class ParsedMeta:
    episode: int | None
    title: str | None
    season: int | None


def normalize_name(name: str) -> str:
    """Normalize anime name for case-insensitive comparison.

    Lowercase, collapse whitespace, strip punctuation and emoji.
    """
    text = name.lower().strip()
    text = unicodedata.normalize("NFKC", text)
    text = _EMOJI_RE.sub("", text)
    text = re.sub(r"[\"'«»\u201c\u201d\[\](){}]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_episode(text: str | None) -> int | None:
    """Mumkin bo'lsa qism raqamini qaytaradi."""
    if not text:
        return None
    for pat in _EPISODE_PATTERNS:
        m = pat.search(text)
        if m:
            return int(m.group(m.lastindex or 1))
    m = re.fullmatch(r"\s*(\d{1,4})\s*", text)
    if m:
        return int(m.group(1))
    return None


def parse_season(text: str | None) -> int | None:
    """Extract season number from text if present."""
    if not text:
        return None
    for pat in _SEASON_PATTERNS:
        m = pat.search(text)
        if m:
            return int(m.group(1))
    return None


def parse_title(text: str | None) -> str | None:
    """Extract anime title from caption text."""
    if not text:
        return None
    lines = text.strip().splitlines()
    content_lines = [ln for ln in lines if not _KANAL_LINE_RE.match(ln)]
    if not content_lines:
        return None
    first_line = content_lines[0].strip()
    cleaned = _STRIP_SUFFIXES.sub("", first_line)
    cleaned = _EMOJI_RE.sub("", cleaned)
    cleaned = re.sub(r"\s*[-—–|]\s*$", "", cleaned)
    cleaned = cleaned.strip("\"'«»\u201c\u201d -\u2014\u2013|[](){}")
    return cleaned or None


def parse_meta(text: str | None) -> ParsedMeta:
    return ParsedMeta(
        episode=parse_episode(text),
        title=parse_title(text),
        season=parse_season(text),
    )
