import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.money import parse_money


def values(text):
    return [a.value for a in parse_money(text)]


@pytest.mark.parametrize(
    "text",
    [
        "$85 000",
        "$85 000",  # no-break space
        "$85 000",  # narrow no-break space
        "85 000",  # thin space
        "85,000",
        "$85,000",
        "85.000",
        "$85k",
        "85K",
        "85к",
        "85 тыс",
        "85 тыс.",
        "85 тысяч",
        "85 mil",
        "85000",
        "eighty-five thousand",
        "Eighty five thousand dollars",
    ],
)
def test_parse_money_reads_85000_in_every_format(text):
    assert values(text) == [85000.0]


@pytest.mark.parametrize(
    "text,expected",
    [
        ("$85,000.50", [85000.5]),
        ("85.000,50", [85000.5]),
        ("85 000,50", [85000.5]),
        ("1.5k", [1500.0]),
        ("$4,650", [4650.0]),
        ("4.5", [4.5]),
        ("$0", [0.0]),
        ("1 200 000", [1200000.0]),
    ],
)
def test_parse_money_decimals_and_suffixes(text, expected):
    assert values(text) == expected


def test_parse_money_keeps_form_and_visa_codes_apart():
    # "1099" is a form number, the amount is separate; W-2 / F-1 digits are not amounts
    assert values("Только 1099: $85 000") == [1099.0, 85000.0]
    assert values("W-2 100 000") == [100000.0]
    assert values("I'm on F-1") == []
    assert values("1099-NEC") == []


def test_parse_money_marks_clear_money_as_explicit():
    explicit = {a.raw.strip(): a.explicit for a in parse_money("2023 and $500 and 85 000 and 12")}
    assert explicit["2023"] is False
    assert explicit["$500"] is True
    assert explicit["85 000"] is True
    assert explicit["12"] is False
