from datetime import date, datetime
from typing import Dict, List, Tuple

from app.config import SCHOLAR_VISAS, STUDENT_VISAS, TAX_YEARS
from app.i18n import tr
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
        exit_date = stay.exit_date or f"{target_year}-12-31"
        start, end = parse_iso_date(stay.entry_date), parse_iso_date(exit_date)
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
                    notes.add(
                        tr(
                            req.language,
                            "student_exempt",
                            visa=v_type,
                            year=prior_total + 1,
                        )
                    )
                else:
                    cnt_days += 1
                    notes.add(tr(req.language, "student_exceeded", visa=v_type))
            elif v_type in SCHOLAR_VISAS:
                if yr == target_year:
                    cur_has_exempt_visa = True
                if prior_six_yr < 2:
                    ex_days += 1
                    used_exempt = True
                    notes.add(
                        tr(
                            req.language,
                            "scholar_exempt",
                            visa=v_type,
                            year=prior_six_yr + 1,
                        )
                    )
                else:
                    cnt_days += 1
                    notes.add(tr(req.language, "scholar_exceeded", visa=v_type))
            else:
                if yr == target_year and v_type in {"H-1B", "L-1", "O-1", "TN", "GREEN_CARD"}:
                    cur_has_work_visa = True
                cnt_days += 1
                notes.add(tr(req.language, "visa_days_count", visa=v_type))

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
                exempt_reason="; ".join(sorted(notes)) if notes else tr(req.language, "no_us_presence"),
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
            label = tr(req.language, "dual_status", year=target_year)
        else:
            res_status = "RESIDENT_ALIEN"
            label = tr(req.language, "resident_status", year=target_year)
    else:
        res_status = "NONRESIDENT_ALIEN"
        label = tr(req.language, "nonresident_status", year=target_year)
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
                title=tr(req.language, "filing_8843_title"),
                mandatory=True,
                deadline=tr(
                    req.language,
                    "standalone_deadline",
                    annual=cfg["annual_deadline"],
                    standalone=cfg["form_8843_deadline"],
                ),
                reason=tr(req.language, "filing_8843_reason", days=cur_exempt_days),
                official_url="https://www.irs.gov/forms-pubs/about-form-8843",
            )
        )

    if res_status == "NONRESIDENT_ALIEN":
        plan.append(
            FilingFormItem(
                form_code="Form 1040-NR",
                title=tr(req.language, "filing_1040nr_title"),
                mandatory=True,
                deadline=cfg["annual_deadline"],
                reason=tr(req.language, "filing_1040nr_reason"),
                official_url="https://www.irs.gov/forms-pubs/about-form-1040-nr",
            )
        )
        if first_year_choice:
            plan.append(
                FilingFormItem(
                    form_code="First-Year Choice (Pub 519)",
                    title=tr(req.language, "filing_first_year_title"),
                    mandatory=False,
                    deadline=cfg["annual_deadline"],
                    reason=tr(
                        req.language,
                        "filing_first_year_reason",
                        days=cur_countable_days,
                        year=target_year,
                        next_year=target_year + 1,
                    ),
                    official_url="https://www.irs.gov/publications/p519",
                )
            )
    elif res_status == "DUAL_STATUS_ALIEN":
        plan.append(
            FilingFormItem(
                form_code="Form 1040 + 1040-NR Statement",
                title=tr(req.language, "filing_dual_title"),
                mandatory=True,
                deadline=cfg["annual_deadline"],
                reason=tr(req.language, "filing_dual_reason"),
                official_url="https://www.irs.gov/individuals/international-taxpayers/taxation-of-dual-status-individuals",
            )
        )
    else:
        plan.append(
            FilingFormItem(
                form_code="Form 1040",
                title=tr(req.language, "filing_1040_title"),
                mandatory=True,
                deadline=cfg["annual_deadline"],
                reason=tr(req.language, "filing_1040_reason"),
                official_url="https://www.irs.gov/forms-pubs/about-form-1040",
            )
        )
        plan.append(
            FilingFormItem(
                form_code="FinCEN Form 114 (FBAR)",
                title=tr(req.language, "filing_fbar_title"),
                mandatory=False,
                deadline=tr(req.language, "fbar_deadline", annual=cfg["annual_deadline"]),
                reason=tr(req.language, "filing_fbar_reason"),
                official_url="https://www.irs.gov/businesses/small-businesses-self-employed/report-of-foreign-bank-and-financial-accounts-fbar",
            )
        )

    if req.closer_connection_eligible and cur_countable_days < 183:
        plan.append(
            FilingFormItem(
                form_code="Form 8840",
                title=tr(req.language, "filing_8840_title"),
                mandatory=True,
                deadline=cfg["annual_deadline"],
                reason=tr(req.language, "filing_8840_reason"),
                official_url="https://www.irs.gov/forms-pubs/about-form-8840",
            )
        )

    if res_status == "NONRESIDENT_ALIEN":
        warnings = [
            tr(req.language, "warning_nonresident_software"),
            tr(req.language, "warning_nonresident_deduction"),
        ]
    elif res_status == "DUAL_STATUS_ALIEN":
        warnings = [
            tr(req.language, "warning_dual_status"),
        ]
    else:
        warnings = [
            tr(
                req.language,
                "warning_resident_deduction",
                amount=cfg["standard_deduction"]["single"],
            ),
        ]

    citations = [
        {"title": tr(req.language, "citation_spt"), "url": "https://www.irs.gov/individuals/international-taxpayers/substantial-presence-test"},
        {"title": tr(req.language, "citation_form_8843"), "url": "https://www.irs.gov/forms-pubs/about-form-8843"},
        {"title": tr(req.language, "citation_fica"), "url": "https://www.irs.gov/individuals/international-taxpayers/foreign-student-liability-for-social-security-and-medicare-taxes"},
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
