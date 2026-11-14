from datetime import date, datetime
from typing import Dict, List, Tuple

from app.config import SCHOLAR_VISAS, STUDENT_VISAS, TAX_YEARS
from app.schemas import FilingFormItem, ResidencyRequest, ResidencyResponse, YearDayBreakdown

VISA_ALIASES = {
    "F1": "F-1",
    "F-1": "F-1",
    "OPT": "OPT",
    "F-1 OPT": "OPT",
    "F1-OPT": "OPT",
    "STEM-OPT": "STEM-OPT",
    "STEM OPT": "STEM-OPT",
    "F-1 STEM OPT": "STEM-OPT",
    "J1": "J-1-STUDENT",
    "J-1": "J-1-STUDENT",
    "J-1 STUDENT": "J-1-STUDENT",
    "J-1 SCHOLAR": "J-1-SCHOLAR",
    "J-1-SCHOLAR": "J-1-SCHOLAR",
    "J-1 TEACHER": "J-1-SCHOLAR",
    "J-1 RESEARCHER": "J-1-SCHOLAR",
    "H1B": "H-1B",
    "H-1B": "H-1B",
    "L1": "L-1",
    "L-1": "L-1",
    "O1": "O-1",
    "O-1": "O-1",
    "GREENCARD": "GREEN_CARD",
    "GREEN-CARD": "GREEN_CARD",
    "GREEN CARD": "GREEN_CARD",
    "LPR": "GREEN_CARD",
}


def parse_iso_date(val: str) -> date:
    return datetime.strptime(val.strip()[:10], "%Y-%m-%d").date()


def normalize_visa(visa: str) -> str:
    cleaned = visa.strip().upper().replace("_", "-")
    return VISA_ALIASES.get(cleaned, cleaned)


def calculate_residency(req: ResidencyRequest) -> ResidencyResponse:
    target_year = req.tax_year if req.tax_year in TAX_YEARS else 2025
    window_years = [target_year - 2, target_year - 1, target_year]
    prior_exempt_years = set(req.prior_exempt_calendar_years)

    stays: List[Tuple[str, date, date]] = []
    has_green_card = req.has_green_card

    for stay in req.stays:
        v_type = normalize_visa(stay.visa_type)
        if v_type == "GREEN_CARD":
            has_green_card = True
        start, end = parse_iso_date(stay.entry_date), parse_iso_date(stay.exit_date)
        if end < start:
            start, end = end, start
        stays.append((v_type, start, end))

        for yr in range(start.year, target_year):
            if max(start, date(yr, 1, 1)) <= min(end, date(yr, 12, 31)):
                if (v_type in STUDENT_VISAS or v_type in SCHOLAR_VISAS) and yr < target_year - 2:
                    prior_exempt_years.add(yr)

    weights = {target_year: 1.0, target_year - 1: 1.0 / 3.0, target_year - 2: 1.0 / 6.0}
    breakdowns: List[YearDayBreakdown] = []

    running_exempt = set(prior_exempt_years)
    exempt_before_target = 0
    cur_exempt_days = 0
    cur_countable_days = 0
    cur_has_work_visa = False
    cur_has_exempt_visa = False

    for yr in window_years:
        if yr == target_year:
            exempt_before_target = sum(1 for y in running_exempt if y < target_year)

        y_start, y_end = date(yr, 1, 1), date(yr, 12, 31)
        day_map: Dict[date, str] = {}

        for v_type, s_date, e_date in stays:
            cur = max(s_date, y_start)
            stop = min(e_date, y_end)
            while cur <= stop:
                existing = day_map.get(cur)
                if existing is None or (existing in STUDENT_VISAS and v_type not in STUDENT_VISAS):
                    day_map[cur] = v_type
                cur = date.fromordinal(cur.toordinal() + 1)

        prior_total = sum(1 for y in running_exempt if y < yr)
        prior_six_yr = sum(1 for y in running_exempt if (yr - 6) <= y < yr)

        ex_days = 0
        cnt_days = 0
        notes = set()
        used_exempt = False

        for v_type in day_map.values():
            if v_type in STUDENT_VISAS:
                if yr == target_year:
                    cur_has_exempt_visa = True
                if prior_total < 5:
                    ex_days += 1
                    used_exempt = True
                    notes.add(f"Student ({v_type}) exempt: year {prior_total + 1} of 5 lifetime calendar years")
                else:
                    cnt_days += 1
                    notes.add(f"Student ({v_type}) exceeded 5-year limit; days count toward SPT")
            elif v_type in SCHOLAR_VISAS:
                if yr == target_year:
                    cur_has_exempt_visa = True
                if prior_six_yr < 2:
                    ex_days += 1
                    used_exempt = True
                    notes.add(f"Scholar ({v_type}) exempt: year {prior_six_yr + 1} of 2 in preceding 6 years")
                else:
                    cnt_days += 1
                    notes.add(f"Scholar ({v_type}) exceeded 2-of-6-year limit; days count toward SPT")
            else:
                if yr == target_year and v_type in {"H-1B", "L-1", "O-1", "TN", "GREEN_CARD"}:
                    cur_has_work_visa = True
                cnt_days += 1
                notes.add(f"Days on {v_type} count 100% toward physical presence")

        if used_exempt or any(v in STUDENT_VISAS or v in SCHOLAR_VISAS for v in day_map.values()):
            running_exempt.add(yr)

        if yr == target_year:
            cur_exempt_days = ex_days
            cur_countable_days = cnt_days

        weight = weights[yr]
        breakdowns.append(
            YearDayBreakdown(
                year=yr,
                total_physical_days=len(day_map),
                exempt_days=ex_days,
                countable_days=cnt_days,
                weight=round(weight, 4),
                weighted_countable_days=round(cnt_days * weight, 2),
                exempt_reason="; ".join(sorted(notes)) if notes else "No US presence recorded",
            )
        )

    breakdowns.sort(key=lambda b: b.year, reverse=True)
    total_weighted = round(sum(b.weighted_countable_days for b in breakdowns), 2)

    meets_spt = (cur_countable_days >= 31) and (total_weighted >= 183.0)
    if req.closer_connection_eligible and cur_countable_days < 183 and not has_green_card:
        meets_spt = False

    dual_status = False
    first_year_choice = False

    if has_green_card or meets_spt:
        if cur_exempt_days > 0 and cur_countable_days > 0:
            dual_status = True
            res_status = "DUAL_STATUS_ALIEN"
            label = f"Dual-Status Alien ({target_year})"
        else:
            res_status = "RESIDENT_ALIEN"
            label = f"Resident Alien for Tax Purposes ({target_year})"
    else:
        res_status = "NONRESIDENT_ALIEN"
        label = f"Nonresident Alien for Tax Purposes ({target_year})"
        if cur_has_work_visa and cur_countable_days >= 31:
            first_year_choice = True

    exempt_active = cur_exempt_days > 0
    fica_exempt = (res_status == "NONRESIDENT_ALIEN") and cur_has_exempt_visa
    india_treaty = (
        res_status in ("NONRESIDENT_ALIEN", "DUAL_STATUS_ALIEN")
        and req.country_of_citizenship.strip().lower() == "india"
        and cur_has_exempt_visa
    )

    cfg = TAX_YEARS[target_year]
    plan: List[FilingFormItem] = []

    if exempt_active:
        plan.append(
            FilingFormItem(
                form_code="Form 8843",
                title="Statement for Exempt Individuals",
                mandatory=True,
                deadline=f"{cfg['annual_deadline']} (or {cfg['form_8843_deadline']} if standalone)",
                reason=f"Required to exclude {cur_exempt_days} exempt days on F/J/M status, even with $0 income.",
                official_url="https://www.irs.gov/forms-pubs/about-form-8843",
            )
        )

    if res_status == "NONRESIDENT_ALIEN":
        plan.append(
            FilingFormItem(
                form_code="Form 1040-NR",
                title="U.S. Nonresident Alien Income Tax Return",
                mandatory=True,
                deadline=cfg["annual_deadline"],
                reason="Required for Nonresident Aliens with U.S.-source income.",
                official_url="https://www.irs.gov/forms-pubs/about-form-1040-nr",
            )
        )
        if first_year_choice:
            plan.append(
                FilingFormItem(
                    form_code="First-Year Choice (Pub 519)",
                    title="Optional Dual-Status Election for Work Visa Transition",
                    mandatory=False,
                    deadline=cfg["annual_deadline"],
                    reason=f"With {cur_countable_days} countable days in {target_year}, you file 1040-NR by default or may elect First-Year Choice after meeting SPT in {target_year + 1}.",
                    official_url="https://www.irs.gov/publications/p519",
                )
            )
    elif res_status == "DUAL_STATUS_ALIEN":
        plan.append(
            FilingFormItem(
                form_code="Form 1040 + 1040-NR Statement",
                title="Dual-Status Tax Return",
                mandatory=True,
                deadline=cfg["annual_deadline"],
                reason="Required when transitioning between Nonresident and Resident status mid-year.",
                official_url="https://www.irs.gov/individuals/international-taxpayers/taxation-of-dual-status-individuals",
            )
        )
    else:
        plan.append(
            FilingFormItem(
                form_code="Form 1040",
                title="U.S. Individual Income Tax Return",
                mandatory=True,
                deadline=cfg["annual_deadline"],
                reason="Taxed as a U.S. Resident on worldwide income.",
                official_url="https://www.irs.gov/forms-pubs/about-form-1040",
            )
        )
        plan.append(
            FilingFormItem(
                form_code="FinCEN Form 114 (FBAR)",
                title="Foreign Bank Account Report (if foreign accounts > $10,000)",
                mandatory=False,
                deadline=f"{cfg['annual_deadline']} (auto-extended to Oct 15)",
                reason="Applies to Resident Aliens with aggregate foreign account balances exceeding $10,000.",
                official_url="https://www.irs.gov/businesses/small-businesses-self-employed/report-of-foreign-bank-and-financial-accounts-fbar",
            )
        )

    if req.closer_connection_eligible and cur_countable_days < 183:
        plan.append(
            FilingFormItem(
                form_code="Form 8840",
                title="Closer Connection Exception Statement",
                mandatory=True,
                deadline=cfg["annual_deadline"],
                reason="Claims Closer Connection exception when weighted days >= 183 but current-year days < 183.",
                official_url="https://www.irs.gov/forms-pubs/about-form-8840",
            )
        )

    if res_status == "NONRESIDENT_ALIEN":
        warnings = [
            "Do not use standard Form 1040 software (TurboTax, FreeTaxUSA) — they do not support Form 1040-NR directly.",
            "Nonresident Aliens cannot claim the federal Standard Deduction unless eligible under US-India Tax Treaty Art. 21(2).",
        ]
    elif res_status == "DUAL_STATUS_ALIEN":
        warnings = [
            "Dual-status returns require a combined Form 1040 / 1040-NR statement and disallow the standard deduction unless married filing jointly with a US resident.",
        ]
    else:
        warnings = [
            f"Resident Aliens qualify for the Standard Deduction (${cfg['standard_deduction']['single']:,.0f} Single) and report worldwide income.",
        ]

    citations = [
        {"title": "IRS Publication 519 — Substantial Presence Test", "url": "https://www.irs.gov/individuals/international-taxpayers/substantial-presence-test"},
        {"title": "IRS Form 8843 Instructions", "url": "https://www.irs.gov/forms-pubs/about-form-8843"},
        {"title": "Foreign Student FICA Tax Exemption (IRC §3121(b)(19))", "url": "https://www.irs.gov/individuals/international-taxpayers/foreign-student-liability-for-social-security-and-medicare-taxes"},
    ]

    return ResidencyResponse(
        tax_year=target_year,
        residency_status=res_status,
        status_label=label,
        meets_substantial_presence_test=meets_spt,
        meets_green_card_test=has_green_card,
        current_year_countable_days=cur_countable_days,
        total_weighted_days=total_weighted,
        spt_threshold_days=183,
        exempt_individual_active=exempt_active,
        exempt_years_used_prior_to_tax_year=exempt_before_target,
        year_breakdown=breakdowns,
        dual_status_detected=dual_status,
        first_year_choice_available=first_year_choice,
        fica_exempt_status=fica_exempt,
        india_treaty_standard_deduction_eligible=india_treaty,
        filing_plan=plan,
        software_warnings=warnings,
        irs_citations=citations,
    )
