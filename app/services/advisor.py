import hashlib
import json
import os
import random
import re
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from app.schemas import (
    ChatAgentRequest,
    CollectedTaxProfile,
    ExplainRequest,
    ResidencyRequest,
    TaxCalculationRequest,
    VisaStay,
    dump_model,
)
from app.services.residency import calculate_residency
from app.services.taxes import calculate_taxes

_CACHE: Dict[str, Tuple[str, str]] = {}
_KEY_INDEX: int = 0


def _get_keys(env_name: str) -> List[str]:
    global _KEY_INDEX
    raw = os.environ.get(env_name, "").strip()
    if not raw:
        return []
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    if len(keys) <= 1:
        return keys
    _KEY_INDEX = (_KEY_INDEX + 1) % len(keys)
    return keys[_KEY_INDEX:] + keys[:_KEY_INDEX]


def _call_chat_completions(
    url: str,
    api_key: str,
    model: str,
    prompt: str,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a US tax assistant for visa holders and 1099 freelancers. "
                    "Explain the provided deterministic numbers clearly without inventing new math."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 600,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "NomadTax/1.0",
    }
    if extra_headers:
        headers.update(extra_headers)

    for attempt in range(2):
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as err:
            if err.code == 429 and attempt == 0:
                time.sleep(0.35 + random.uniform(0.05, 0.2))
                continue
            break
        except Exception:
            break
    return None


def call_llm(prompt: str) -> Tuple[Optional[str], str]:
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    if digest in _CACHE:
        return _CACHE[digest]

    providers = [
        (
            "OPENROUTER_API_KEY",
            "https://openrouter.ai/api/v1/chat/completions",
            os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
            "openrouter",
            {"HTTP-Referer": "https://nomadtax.vercel.app", "X-Title": "NomadTax"},
        ),
        (
            "OPENAI_API_KEY",
            "https://api.openai.com/v1/chat/completions",
            os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            "openai",
            None,
        ),
        (
            "DEEPSEEK_API_KEY",
            "https://api.deepseek.com/chat/completions",
            "deepseek-chat",
            "deepseek",
            None,
        ),
        (
            "GROQ_API_KEY",
            "https://api.groq.com/openai/v1/chat/completions",
            "llama-3.3-70b-versatile",
            "groq",
            None,
        ),
    ]

    for env_var, endpoint, model, label, headers in providers:
        for key in _get_keys(env_var):
            text = _call_chat_completions(endpoint, key, model, prompt, headers)
            if text:
                res = (text, f"{label}:{model}")
                _CACHE[digest] = res
                return res

    for key in _get_keys("GEMINI_API_KEY"):
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
            body = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 700},
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                res = (text, "gemini:gemini-2.5-flash")
                _CACHE[digest] = res
                return res
        except Exception:
            continue

    return None, "deterministic-irs-explainer"


def generate_explanation(req: ExplainRequest) -> Dict[str, Any]:
    lang = req.language.lower()
    res = req.residency_result or {}
    tax = req.tax_result or {}

    prompt = (
        f"Explain these US tax results in {'Russian' if lang == 'ru' else 'English'} in 3 short bullet points "
        f"(1. Residency status & day count, 2. Tax liability & deduction savings, 3. Forms & deadlines).\n"
        f"Residency: {json.dumps(res, ensure_ascii=False)}\n"
        f"Taxes: {json.dumps(tax, ensure_ascii=False)}\n"
        f"Question: {req.user_question or 'None'}"
    )

    text, provider = call_llm(prompt)
    if not text:
        status = res.get("residency_status", tax.get("residency_status", "RESIDENT_ALIEN"))
        w_days = res.get("total_weighted_days", 0)
        c_days = res.get("current_year_countable_days", 0)
        tot_tax = tax.get("total_tax_liability", 0.0)
        saved = tax.get("Deduction_tax_savings_usd", 0.0)
        fica_ref = tax.get("erroneous_fica_refund_amount", 0.0)

        if lang == "ru":
            parts = [
                f"**Налоговый статус ({status}):** Зачётных дней в текущем году — **{c_days}**, взвешенных за 3 года — **{w_days}** (порог 183 дня по IRS Pub 519)."
            ]
            if tax:
                msg = f"**Налоги и вычеты:** Итоговый налог — **${tot_tax:,.2f}**, экономия за счёт бизнес-вычетов — **${saved:,.2f}**."
                if fica_ref > 0:
                    msg += f" Обнаружено ошибочное удержание FICA на **${fica_ref:,.2f}** (возврат через Form 843 и Form 8316)."
                parts.append(msg)
            parts.append("**Следующий шаг:** Скачайте Form 8843 и проверьте график квартальных платежей Form 1040-ES.")
            text = "\n\n".join(parts)
        else:
            parts = [
                f"**Tax Residency ({status}):** You have **{c_days} countable days** this year and **{w_days} weighted days** over 3 years (183-day threshold under IRS Pub 519)."
            ]
            if tax:
                msg = f"**Taxes & Savings:** Total estimated tax is **${tot_tax:,.2f}**, with **${saved:,.2f}** saved via business deductions."
                if fica_ref > 0:
                    msg += f" Erroneous FICA withholding of **${fica_ref:,.2f}** detected (recoverable via Form 843 & Form 8316)."
                parts.append(msg)
            parts.append("**Next Steps:** Download your pre-filled Form 8843 PDF and review your Form 1040-ES quarterly schedule.")
            text = "\n\n".join(parts)

    return {
        "provider": provider,
        "language": lang,
        "explanation_markdown": text,
        "disclaimer": "Informational calculation based on IRS Publication 519; not formal CPA or legal advice.",
    }


def _extract_slots(message: str, profile: CollectedTaxProfile) -> CollectedTaxProfile:
    up = message.upper()
    visa_rules = [
        (r"\bSTEM[-\s]?OPT\b", "STEM-OPT"),
        (r"\bOPT\b", "OPT"),
        (r"\bF[-\s]?1\b|\bФ[-\s]?1\b", "F-1"),
        (r"\bH[-\s]?1B\b|\bН[-\s]?1В\b", "H-1B"),
        (r"\bJ[-\s]?1\b", "J-1-STUDENT"),
        (r"\bO[-\s]?1\b", "O-1"),
        (r"\bL[-\s]?1\b", "L-1"),
        (r"\bTN\b", "TN"),
        (r"\bB[-\s]?1|\bB[-\s]?2|\bТУРИСТ", "B-1/B-2"),
        (r"GREEN\s*CARD|ГРИН\s*КАРТ|LPR", "GREEN_CARD"),
    ]
    for pat, code in visa_rules:
        if re.search(pat, up):
            profile.visa_type = code
            break

    iso = re.search(r"\b(20[12]\d-[01]\d-[0-3]\d)\b", message)
    if iso:
        profile.entry_date = iso.group(1)
    elif not profile.entry_date:
        yr = re.search(r"\b(201[89]|202[0-6])\b", message)
        if yr:
            months = {
                "янв": "01", "jan": "01", "фев": "02", "feb": "02", "мар": "03", "mar": "03",
                "апр": "04", "apr": "04", "ма": "05", "may": "05", "июн": "06", "jun": "06",
                "июл": "07", "jul": "07", "авг": "08", "aug": "08", "сен": "09", "sep": "09",
                "окт": "10", "oct": "10", "ноя": "11", "nov": "11", "дек": "12", "dec": "12",
            }
            m_code = "08"
            low = message.lower()
            for prefix, num in months.items():
                if prefix in low:
                    m_code = num
                    break
            profile.entry_date = f"{yr.group(1)}-{m_code}-15"

    countries = {
        "инди": "India", "india": "India", "казах": "Kazakhstan", "kazakh": "Kazakhstan",
        "украин": "Ukraine", "ukrain": "Ukraine", "росси": "Russia", "russia": "Russia",
        "узбек": "Uzbekistan", "uzbek": "Uzbekistan", "кита": "China", "china": "China",
    }
    low = message.lower()
    for prefix, cname in countries.items():
        if prefix in low:
            profile.country_of_citizenship = cname
            break

    if any(w in low for w in ["нет дохода", "no income", "0 доход", "$0", "нулевой доход"]):
        if profile.gross_1099_income is None:
            profile.gross_1099_income = 0.0
        if profile.w2_wages is None:
            profile.w2_wages = 0.0

    for match in re.finditer(r"(\$?\s*\d+(?:[.,]\d+)?\s*(?:k|к|тыс)?)", low):
        tok = match.group(1).replace("$", "").replace(",", "").strip()
        mult = 1000.0 if tok.endswith(("k", "к", "тыс")) else 1.0
        tok = re.sub(r"(?:k|к|тыс)$", "", tok).strip()
        try:
            val = float(tok) * mult
        except ValueError:
            continue
        if val in (1099, 8843, 1040, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026, 2027, 1, 2):
            continue
        ctx = low[max(0, match.start() - 20) : min(len(low), match.end() + 10)]
        if any(k in ctx for k in ["расход", "вычет", "deduct", "expense", "трат"]):
            profile.business_deductions = val
        elif any(k in ctx for k in ["fica", "фика", "social security", "medicare"]):
            profile.w2_fica_withheld = val
        elif any(k in ctx for k in ["w-2", "w2", "зарплат", "salary", "wage"]):
            profile.w2_wages = val
        elif any(k in ctx for k in ["1099", "фриланс", "freelance", "самозан", "доход", "заработ", "earned", "income"]):
            profile.gross_1099_income = val
        elif profile.gross_1099_income is None and val >= 300:
            profile.gross_1099_income = val

    return profile


def run_chat_turn(req: ChatAgentRequest) -> Dict[str, Any]:
    lang = req.language.lower()
    profile = req.collected_profile or CollectedTaxProfile()

    for msg in req.messages:
        if msg.role == "user":
            profile = _extract_slots(msg.content, profile)

    missing: List[str] = []
    if not profile.visa_type:
        missing.append("visa_type")
    if not profile.entry_date:
        missing.append("entry_date")
    if profile.gross_1099_income is None and profile.w2_wages is None:
        missing.append("income_sources")
    if profile.gross_1099_income and profile.gross_1099_income > 0 and profile.business_deductions is None:
        missing.append("business_deductions")

    live_res: Optional[Dict[str, Any]] = None
    live_tax: Optional[Dict[str, Any]] = None

    if profile.visa_type:
        entry_dt = profile.entry_date or f"{profile.tax_year - 2}-08-20"
        entry_yr = int(entry_dt[:4])
        stays = [
            VisaStay(
                visa_type=profile.visa_type,
                entry_date=entry_dt if y == entry_yr else f"{y}-01-01",
                exit_date=f"{y}-12-31",
            )
            for y in range(max(entry_yr, profile.tax_year - 2), profile.tax_year + 1)
        ]
        res_obj = calculate_residency(
            ResidencyRequest(
                tax_year=profile.tax_year,
                stays=stays,
                prior_exempt_calendar_years=list(range(entry_yr, profile.tax_year - 2)),
                country_of_citizenship=profile.country_of_citizenship or "Kazakhstan",
            )
        )
        live_res = dump_model(res_obj)

        if profile.gross_1099_income is not None or profile.w2_wages is not None:
            tax_obj = calculate_taxes(
                TaxCalculationRequest(
                    tax_year=profile.tax_year,
                    filing_status="single",
                    residency_status=res_obj.residency_status,
                    visa_type=profile.visa_type,
                    country_of_citizenship=profile.country_of_citizenship or "Kazakhstan",
                    gross_1099_income=profile.gross_1099_income or 0.0,
                    business_deductions=profile.business_deductions or 0.0,
                    w2_wages=profile.w2_wages or 0.0,
                    w2_federal_withheld=profile.w2_federal_withheld or 0.0,
                    w2_fica_withheld=profile.w2_fica_withheld or 0.0,
                )
            )
            live_tax = dump_model(tax_obj)

    last_msg = req.messages[-1].content if req.messages else ""
    prompt = (
        f"You are NomadTax AI speaking {'Russian' if lang == 'ru' else 'English'}.\n"
        f"User message: {last_msg}\n"
        f"Profile: {json.dumps(dump_model(profile), ensure_ascii=False)}\n"
        f"Missing fields: {missing}\n"
        f"Calculated Residency: {json.dumps(live_res, ensure_ascii=False)}\n"
        f"Calculated Taxes: {json.dumps(live_tax, ensure_ascii=False)}\n"
        f"Reply in 2-3 concise sentences. If missing fields exist, ask for the first missing field. Otherwise summarize the result."
    )
    reply, provider = call_llm(prompt)

    if not reply:
        if "visa_type" in missing:
            reply = (
                "На какой визе или в каком статусе ты находишься в США (например, F-1, OPT, H-1B, O-1, J-1)?"
                if lang == "ru"
                else "What visa or status are you currently on in the US (e.g., F-1, OPT, H-1B, O-1, J-1)?"
            )
        elif "entry_date" in missing:
            reply = (
                f"Статус {profile.visa_type} учтён. В каком году и месяце ты впервые въехал в США по этому статусу?"
                if lang == "ru"
                else f"Got it ({profile.visa_type}). When did you first enter the US in this status?"
            )
        elif "income_sources" in missing:
            st = live_res["residency_status"] if live_res else "NONRESIDENT_ALIEN"
            reply = (
                f"Предварительный статус — {st}. Какой доход был за год по 1099 / фрилансу и по W-2 (или $0)?"
                if lang == "ru"
                else f"Preliminary status is {st}. How much income did you earn from 1099 freelancing and/or W-2 wages?"
            )
        elif "business_deductions" in missing:
            reply = (
                f"Доход по 1099 (${profile.gross_1099_income:,.0f}) записан. Какая сумма рабочих расходов (техника, софт, облака, поездки) была за год?"
                if lang == "ru"
                else f"Recorded ${profile.gross_1099_income:,.0f} in 1099 income. How much did you spend on deductible work expenses?"
            )
        else:
            tot = live_tax["total_tax_liability"] if live_tax else 0.0
            saved = live_tax["Deduction_tax_savings_usd"] if live_tax else 0.0
            st = live_res["residency_status"] if live_res else "NONRESIDENT_ALIEN"
            reply = (
                f"Расчёт готов: статус — {st}, итоговый налог — ${tot:,.2f}, экономия на вычетах — ${saved:,.2f}."
                if lang == "ru"
                else f"Calculation complete: status is {st}, estimated tax is ${tot:,.2f}, and deductions saved ${saved:,.2f}."
            )

    if "visa_type" in missing:
        chips = ["F-1 Student", "F-1 OPT", "H-1B", "O-1 / Freelancer", "J-1 Scholar"]
    elif "entry_date" in missing:
        chips = ["Август 2023 (2023-08-20)", "Август 2024 (2024-08-25)", "Январь 2020 (2020-01-15)"]
    elif "income_sources" in missing:
        chips = ["$28,000 по 1099 и $45,000 по W-2", "Только 1099: $85,000", "Дохода не было ($0)"]
    elif "business_deductions" in missing:
        chips = ["Расходы $4,650", "Расходы $12,000", "Расходов не было ($0)"]
    else:
        chips = ["Скачать PDF Form 8843", "Почему нельзя TurboTax?", "Как вернуть FICA?"]

    return {
        "reply": reply,
        "provider": provider,
        "collected_profile": dump_model(profile),
        "missing_fields": missing,
        "is_complete": len(missing) == 0,
        "suggested_replies": chips,
        "live_calculation": {
            "residency": live_res,
            "taxes": live_tax,
            "form_8843_ready": bool(live_res and live_res.get("exempt_individual_active")),
        },
    }
