"""The one place where money amounts are read from free text (EN/RU/ES).

parse_money("Только 1099: $85 000") -> [Amount(value=1099.0, ...), Amount(value=85000.0, ...)]

Handles thousands separators (space, no-break space U+00A0, narrow no-break space U+202F,
thin space U+2009, comma, dot), decimals ("$85,000.50", "85.000,50"), suffixes
("85k", "85к", "85 тыс", "85 тысяч", "85 mil", "1.5k") and English number words
("eighty-five thousand").
"""

import re
from dataclasses import dataclass
from typing import List, Optional

_SPACES = "    "
_SP = f"[{_SPACES}]"

# number core: grouped thousands (space/comma/dot) or plain digits, optional decimals
_NUMBER = re.compile(
    rf"""
    (?<![\w\-./])                              # not part of W-2, F-1, 1099-NEC, dates, decimals
    (?P<currency>\$\s?)?
    (?P<num>
        \d{{1,3}}(?:{_SP}\d{{3}})+(?:[.,]\d{{1,2}})?   # 85 000 / 85 000,50
      | \d{{1,3}}(?:,\d{{3}})+(?:\.\d{{1,2}})?         # 85,000 / 85,000.50
      | \d{{1,3}}(?:\.\d{{3}})+(?:,\d{{1,2}})?         # 85.000 / 85.000,50
      | \d+(?:[.,]\d+)?                                # 85000 / 4.5
    )
    (?P<suffix>{_SP}?(?:тысяч[аи]?|тыс\.?|thousand|mil\b|k\b|к\b|K\b))?
    (?![\w\-])
    """,
    re.VERBOSE | re.IGNORECASE,
)


@dataclass
class Amount:
    value: float
    start: int
    end: int
    raw: str
    explicit: bool  # has a currency sign, a thousands suffix or separators (clearly money)


def _to_float(num: str) -> float:
    s = re.sub(f"[{_SPACES}]", "", num)
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?", s):  # 85,000.50
        return float(s.replace(",", ""))
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?", s):  # 85.000,50
        return float(s.replace(".", "").replace(",", "."))
    if re.fullmatch(r"\d+,\d{1,2}", s):  # 4,5 (decimal comma)
        return float(s.replace(",", "."))
    return float(s.replace(",", ""))


_UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
_WORD = "|".join(list(_UNITS) + list(_TENS) + ["hundred", "thousand", "and"])
_WORDS = re.compile(rf"\b(?:{_WORD})(?:[\s-]+(?:{_WORD}))*\b", re.IGNORECASE)


def _words_to_number(text: str) -> Optional[float]:
    total, current, seen = 0, 0, False
    for word in re.split(r"[\s-]+", text.lower()):
        if word == "and":
            continue
        if word in _UNITS:
            current += _UNITS[word]
        elif word in _TENS:
            current += _TENS[word]
        elif word == "hundred":
            current = (current or 1) * 100
        elif word == "thousand":
            total += (current or 1) * 1000
            current = 0
        else:
            return None
        seen = True
    return float(total + current) if seen else None


def parse_money(text: str) -> List[Amount]:
    """All amounts in the text, in order of appearance."""
    found: List[Amount] = []
    for m in _NUMBER.finditer(text):
        value = _to_float(m.group("num"))
        suffix = (m.group("suffix") or "").strip().lower()
        if suffix:
            value *= 1000
        grouped = bool(re.search(f"[{_SPACES},.]\\d{{3}}(?!\\d)", m.group("num")))
        found.append(
            Amount(
                value=round(value, 2),
                start=m.start(),
                end=m.end(),
                raw=m.group(0),
                explicit=bool(m.group("currency") or suffix or grouped),
            )
        )
    for m in _WORDS.finditer(text):
        if not re.search(r"hundred|thousand|ty\b|teen\b", m.group(0), re.IGNORECASE):
            continue  # skip lone small words like "one" in "one more question"
        value = _words_to_number(m.group(0))
        if value:
            found.append(Amount(value=value, start=m.start(), end=m.end(), raw=m.group(0), explicit=True))
    found.sort(key=lambda a: a.start)
    return found
