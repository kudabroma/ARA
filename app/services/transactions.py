import csv
import io
import re
from typing import Dict, List, Optional, Tuple

from app.schemas import (
    CategorizedTransaction,
    TransactionInput,
    TransactionsAnalyzeRequest,
    TransactionsAnalyzeResponse,
)

RULES: List[Tuple[str, str, Optional[str], float, str]] = [
    (
        r"stripe|upwork|fiverr|toptal|deel|gusto|payoneer|patreon|youtube|twitch|substack|client|invoice|1099|payout|consulting",
        "INCOME_1099",
        None,
        0.0,
        "1099 contractor payout or creator revenue",
    ),
    (
        r"aws|amazon web services|vercel|supabase|github|openai|anthropic|cursor|figma|notion|linear|cloudflare|digitalocean|heroku|google cloud|namecheap|godaddy|zoom|slack|adobe",
        "BUSINESS_DEDUCTION",
        "Software & Cloud Infrastructure (Schedule C Line 18/27a)",
        1.0,
        "100% deductible software or cloud subscription",
    ),
    (
        r"apple store|macbook|dell|lenovo|bh photo|best buy|logitech|keychron|monitor",
        "BUSINESS_DEDUCTION",
        "Equipment & Section 179 (Schedule C Line 13)",
        1.0,
        "100% deductible work hardware under Section 179",
    ),
    (
        r"wework|regus|coworking|industrious|hub|office depot|staples",
        "BUSINESS_DEDUCTION",
        "Coworking & Office Expenses (Schedule C Line 18/20b)",
        1.0,
        "100% deductible workspace rent or office supplies",
    ),
    (
        r"comcast|xfinity|at&t|verizon|t-mobile|spectrum|starlink",
        "BUSINESS_DEDUCTION",
        "Business Phone & Internet (Schedule C Line 25)",
        0.50,
        "50% business-use allocation for phone and internet",
    ),
    (
        r"united airlines|delta|american airlines|southwest|jetblue|airbnb|marriott|hilton|hyatt|amtrak|uber|lyft|waymo",
        "BUSINESS_DEDUCTION",
        "Business Travel & Transit (Schedule C Line 24a)",
        1.0,
        "100% deductible business travel and transit",
    ),
    (
        r"meta ads|google ads|linkedin ads|x ads|mailchimp|convertkit|ahrefs|semrush",
        "BUSINESS_DEDUCTION",
        "Advertising & Marketing (Schedule C Line 8)",
        1.0,
        "100% deductible marketing expense",
    ),
    (
        r"legalzoom|stripe atlas|cpa|sprintax|accounting|lawyer|usps|fedex|ups|dhl",
        "BUSINESS_DEDUCTION",
        "Legal & Professional Services (Schedule C Line 17)",
        1.0,
        "100% deductible legal, accounting, or mailing expense",
    ),
    (
        r"starbucks|blue bottle|panera|sweetgreen|chipotle|client dinner|client lunch|restaurant|cafe",
        "BUSINESS_DEDUCTION",
        "Business Meals (Schedule C Line 24b — 50% Rule)",
        0.50,
        "50% deductible business meal under IRC §274(n)",
    ),
    (
        r"netflix|spotify|hulu|steam|faceit|playstation|xbox|whole foods|trader joe|kroger|target|walmart|zara|nike|gym|equinox|planet fitness|rent|apartment|doordash|wolt|uber eats",
        "PERSONAL",
        None,
        0.0,
        "Personal living or entertainment expense",
    ),
]


def parse_csv_rows(raw_csv: str) -> List[TransactionInput]:
    rows: List[TransactionInput] = []
    reader = csv.DictReader(io.StringIO(raw_csv.strip()))
    for idx, row in enumerate(reader):
        clean = {k.strip().lower(): (v.strip() if v else "") for k, v in row.items() if k}
        desc = clean.get("description") or clean.get("merchant") or clean.get("name") or f"Transaction #{idx + 1}"
        dt = clean.get("date") or clean.get("posted_date") or "2025-06-15"
        amt_str = re.sub(r"[^0-9.\-]", "", clean.get("amount") or clean.get("usd") or "0")
        try:
            amt = float(amt_str)
        except ValueError:
            amt = 0.0
        hint = clean.get("type") or ("income" if amt > 0 and "deposit" in desc.lower() else None)
        rows.append(TransactionInput(id=f"csv-{idx + 1}", date=dt, description=desc, amount=abs(amt), type_hint=hint))
    return rows


def analyze_transactions(req: TransactionsAnalyzeRequest) -> TransactionsAnalyzeResponse:
    items = list(req.transactions)
    if req.csv_text:
        items.extend(parse_csv_rows(req.csv_text))

    categorized: List[CategorizedTransaction] = []
    inc_total = 0.0
    exp_raw = 0.0
    ded_total = 0.0
    pers_total = 0.0
    by_category: Dict[str, float] = {}

    for idx, tx in enumerate(items):
        tx_id = tx.id or f"tx-{idx + 1}"
        desc_low = tx.description.lower()
        amt = round(abs(tx.amount), 2)

        cls_name = "PERSONAL"
        cat_name: Optional[str] = None
        pct = 0.0
        reason = "Personal expense (no business rule matched)"

        if tx.type_hint and tx.type_hint.lower() == "income":
            cls_name = "INCOME_1099"
            reason = "1099 income payout"
        else:
            for pattern, matched_cls, sched_c, ded_pct, r_text in RULES:
                if re.search(pattern, desc_low):
                    cls_name = matched_cls
                    cat_name = sched_c
                    pct = ded_pct
                    reason = r_text
                    break

        ded_amt = round(amt * pct, 2) if cls_name == "BUSINESS_DEDUCTION" else 0.0
        saved = round(ded_amt * req.marginal_tax_rate_estimate, 2)

        if cls_name == "INCOME_1099":
            inc_total += amt
        elif cls_name == "BUSINESS_DEDUCTION":
            exp_raw += amt
            ded_total += ded_amt
            key = cat_name or "Other Business Expenses"
            by_category[key] = round(by_category.get(key, 0.0) + ded_amt, 2)
        else:
            pers_total += amt

        categorized.append(
            CategorizedTransaction(
                id=tx_id,
                date=tx.date,
                description=tx.description,
                amount=amt,
                classification=cls_name,
                schedule_c_category=cat_name,
                deductible_percentage=pct,
                deductible_amount=ded_amt,
                estimated_tax_saved=saved,
                reason=reason,
            )
        )

    return TransactionsAnalyzeResponse(
        total_income_1099=round(inc_total, 2),
        total_business_expenses_raw=round(exp_raw, 2),
        total_deductible_expenses=round(ded_total, 2),
        total_personal_expenses=round(pers_total, 2),
        estimated_total_tax_savings=round(ded_total * req.marginal_tax_rate_estimate, 2),
        category_summary=by_category,
        transactions=categorized,
    )
