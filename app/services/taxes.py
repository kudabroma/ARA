from typing import List, Tuple

from app.config import SCHOLAR_VISAS, STUDENT_VISAS, TAX_YEARS
from app.schemas import (
    BracketBreakdownItem,
    QuarterlyPaymentItem,
    TaxCalculationRequest,
    TaxCalculationResponse,
    copy_model,
)
from app.services.residency import normalize_visa


def _progressive_tax(
    taxable_income: float, brackets: List[Tuple[float, float]]
) -> Tuple[float, List[BracketBreakdownItem]]:
    if taxable_income <= 0:
        return 0.0, []

    total = 0.0
    floor = 0.0
    rows: List[BracketBreakdownItem] = []

    for ceiling, rate in brackets:
        if taxable_income <= floor:
            break
        band = min(taxable_income, ceiling) - floor
        tax_band = round(band * rate, 2)
        total += tax_band
        rows.append(
            BracketBreakdownItem(
                rate_percent=round(rate * 100, 1),
                bracket_floor=floor,
                bracket_ceiling=None if ceiling == float("inf") else ceiling,
                taxable_in_bracket=round(band, 2),
                tax_amount=tax_band,
            )
        )
        floor = ceiling

    return round(total, 2), rows


def calculate_taxes(req: TaxCalculationRequest) -> TaxCalculationResponse:
    year = req.tax_year if req.tax_year in TAX_YEARS else 2025
    cfg = TAX_YEARS[year]
    status = req.filing_status.lower()
    if status not in cfg["brackets"]:
        status = "single"

    res_status = req.residency_status.upper()
    v_type = normalize_visa(req.visa_type)

    net_se = max(0.0, round(req.gross_1099_income - req.business_deductions, 2))
    se_exempt = res_status == "NONRESIDENT_ALIEN"

    if se_exempt or net_se < 400.0:
        se_tax = 0.0
        se_half = 0.0
    else:
        se_base = round(net_se * 0.9235, 2)
        ss_cap_left = max(0.0, cfg["ss_wage_base"] - req.w2_wages)
        ss_tax = min(se_base, ss_cap_left) * 0.124
        med_tax = se_base * 0.029
        add_med_limit = 250000.0 if status == "married_joint" else 200000.0
        add_med = max(0.0, (req.w2_wages + se_base) - add_med_limit) * 0.009
        se_tax = round(ss_tax + med_tax + add_med, 2)
        se_half = round((ss_tax + med_tax) * 0.5, 2)

    gross_combined = round(req.w2_wages + net_se, 2)
    agi = max(0.0, round(gross_combined - se_half, 2))

    india_student = req.country_of_citizenship.strip().lower() == "india" and v_type in STUDENT_VISAS
    if res_status == "RESIDENT_ALIEN":
        std_ded = cfg["standard_deduction"][status]
        note = f"Resident Alien (Form 1040): {year} Standard Deduction (${std_ded:,.0f}) applied."
    elif res_status == "NONRESIDENT_ALIEN" and india_student:
        std_ded = cfg["standard_deduction"]["single"]
        note = f"Nonresident Alien (Form 1040-NR): Standard deduction (${std_ded:,.0f}) applied via US-India Tax Treaty Art. 21(2)."
    else:
        std_ded = 0.0
        note = "Nonresident / Dual-Status (Form 1040-NR): Standard deduction ($0) per IRC §63(c)(6)(B)."

    pre_qbi = max(0.0, agi - std_ded)
    qbi_eligible = max(0.0, net_se - se_half)
    qbi_ded = round(min(qbi_eligible * 0.20, pre_qbi * 0.20), 2) if qbi_eligible > 0 else 0.0

    taxable = max(0.0, round(pre_qbi - qbi_ded, 2))
    bracket_key = "single" if res_status == "NONRESIDENT_ALIEN" else status
    fed_tax, breakdown = _progressive_tax(taxable, cfg["brackets"][bracket_key])

    total_tax = round(fed_tax + se_tax, 2)
    gross_raw = req.w2_wages + req.gross_1099_income
    eff_rate = round((total_tax / gross_raw) * 100, 2) if gross_raw > 0 else 0.0

    if req.business_deductions > 0:
        no_ded_req = copy_model(req, {"business_deductions": 0.0})
        no_ded_res = calculate_taxes(no_ded_req)
        ded_savings = max(0.0, round(no_ded_res.total_tax_liability - total_tax, 2))
    else:
        ded_savings = 0.0

    fica_refund = 0.0
    fica_msg = None
    if res_status == "NONRESIDENT_ALIEN" and v_type in (STUDENT_VISAS | SCHOLAR_VISAS) and req.w2_fica_withheld > 0:
        fica_refund = round(req.w2_fica_withheld, 2)
        fica_msg = (
            f"Nonresident {v_type} holders are exempt from Social Security and Medicare taxes under IRC §3121(b)(19). "
            f"You can claim a ${fica_refund:,.2f} refund using IRS Form 843 and Form 8316."
        )

    paid = req.w2_federal_withheld + req.estimated_payments_already_made
    net_balance = round(total_tax - paid, 2)
    per_quarter = round(max(0.0, net_balance) / 4.0, 2)

    schedule = [
        QuarterlyPaymentItem(
            quarter=q["quarter"],
            period=q["period"],
            due_date=q["due_date"],
            amount_due=per_quarter,
        )
        for q in cfg["quarterly_deadlines"]
    ]

    return TaxCalculationResponse(
        tax_year=year,
        residency_status=res_status,
        filing_status=status,
        gross_total_income=round(gross_raw, 2),
        net_self_employment_income=net_se,
        self_employment_tax=se_tax,
        se_tax_deductible_half=se_half,
        se_tax_exempt_nonresident=se_exempt,
        adjusted_gross_income=agi,
        standard_deduction_applied=std_ded,
        qbi_deduction_applied=qbi_ded,
        taxable_income=taxable,
        federal_income_tax=fed_tax,
        total_tax_liability=total_tax,
        effective_tax_rate_percent=eff_rate,
        Deduction_tax_savings_usd=ded_savings,
        w2_federal_withheld=req.w2_federal_withheld,
        erroneous_fica_refund_amount=fica_refund,
        erroneous_fica_explanation=fica_msg,
        net_tax_owed_or_refund=net_balance,
        is_refund=net_balance < 0,
        recommended_monthly_set_aside=round(max(0.0, net_balance) / 12.0, 2),
        quarterly_schedule=schedule,
        bracket_breakdown=breakdown,
        irs_direct_pay_url="https://www.irs.gov/payments/direct-pay",
        filing_status_note=note,
    )
