from typing import Any, Dict, Set

# The app works on one tax year; 2025 stays supported for explicit API requests.
DEFAULT_TAX_YEAR = 2026

STUDENT_VISAS: Set[str] = {"F-1", "F-2", "OPT", "STEM-OPT", "J-1-STUDENT", "M-1", "M-2", "Q-1"}
SCHOLAR_VISAS: Set[str] = {"J-1-SCHOLAR", "J-1-TEACHER", "J-1-RESEARCHER", "J-2"}
WORK_VISAS: Set[str] = {"H-1B", "H-4", "L-1", "L-2", "O-1", "TN", "E-2", "B-1/B-2", "ESTA", "OTHER"}

TAX_YEARS: Dict[int, Dict[str, Any]] = {
    2025: {
        "standard_deduction": {
            "single": 15750.0,
            "married_joint": 31500.0,
            "married_separate": 15750.0,
            "head_of_household": 23625.0,
        },
        "ss_wage_base": 176100.0,
        "brackets": {
            "single": [
                (11925.0, 0.10),
                (48475.0, 0.12),
                (103350.0, 0.22),
                (197300.0, 0.24),
                (250525.0, 0.32),
                (626350.0, 0.35),
                (float("inf"), 0.37),
            ],
            "married_joint": [
                (23850.0, 0.10),
                (96950.0, 0.12),
                (206700.0, 0.22),
                (394600.0, 0.24),
                (501050.0, 0.32),
                (751600.0, 0.35),
                (float("inf"), 0.37),
            ],
            "married_separate": [
                (11925.0, 0.10),
                (48475.0, 0.12),
                (103350.0, 0.22),
                (197300.0, 0.24),
                (250525.0, 0.32),
                (375800.0, 0.35),
                (float("inf"), 0.37),
            ],
            "head_of_household": [
                (17000.0, 0.10),
                (64850.0, 0.12),
                (103350.0, 0.22),
                (197300.0, 0.24),
                (250500.0, 0.32),
                (626350.0, 0.35),
                (float("inf"), 0.37),
            ],
        },
        "quarterly_deadlines": [
            {"quarter": "Q1", "period": "Jan 1 – Mar 31, 2025", "due_date": "2025-04-15"},
            {"quarter": "Q2", "period": "Apr 1 – May 31, 2025", "due_date": "2025-06-16"},
            {"quarter": "Q3", "period": "Jun 1 – Aug 31, 2025", "due_date": "2025-09-15"},
            {"quarter": "Q4", "period": "Sep 1 – Dec 31, 2025", "due_date": "2026-01-15"},
        ],
        "annual_deadline": "2026-04-15",
        "form_8843_deadline": "2026-06-15",
    },
    2026: {
        "standard_deduction": {
            "single": 16100.0,
            "married_joint": 32200.0,
            "married_separate": 16100.0,
            "head_of_household": 24150.0,
        },
        "ss_wage_base": 184500.0,
        "brackets": {
            "single": [
                (12400.0, 0.10),
                (50400.0, 0.12),
                (105700.0, 0.22),
                (201775.0, 0.24),
                (256225.0, 0.32),
                (640600.0, 0.35),
                (float("inf"), 0.37),
            ],
            "married_joint": [
                (24800.0, 0.10),
                (100800.0, 0.12),
                (211400.0, 0.22),
                (403550.0, 0.24),
                (512450.0, 0.32),
                (768700.0, 0.35),
                (float("inf"), 0.37),
            ],
            "married_separate": [
                (12400.0, 0.10),
                (50400.0, 0.12),
                (105700.0, 0.22),
                (201775.0, 0.24),
                (256225.0, 0.32),
                (384350.0, 0.35),
                (float("inf"), 0.37),
            ],
            "head_of_household": [
                (17700.0, 0.10),
                (67450.0, 0.12),
                (105700.0, 0.22),
                (201750.0, 0.24),
                (256200.0, 0.32),
                (640600.0, 0.35),
                (float("inf"), 0.37),
            ],
        },
        "quarterly_deadlines": [
            {"quarter": "Q1", "period": "Jan 1 – Mar 31, 2026", "due_date": "2026-04-15"},
            {"quarter": "Q2", "period": "Apr 1 – May 31, 2026", "due_date": "2026-06-15"},
            {"quarter": "Q3", "period": "Jun 1 – Aug 31, 2026", "due_date": "2026-09-15"},
            {"quarter": "Q4", "period": "Sep 1 – Dec 31, 2026", "due_date": "2027-01-15"},
        ],
        "annual_deadline": "2027-04-15",
        "form_8843_deadline": "2027-06-15",
    },
}
