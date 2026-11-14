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
from app import faq
from app.i18n import normalize_language, tr
from app.services.residency import calculate_residency
from app.services.taxes import calculate_taxes

_CACHE: Dict[str, Tuple[str, str]] = {}
_KEY_INDEX: int = 0

_LANGUAGE_NAMES = {"en": "English", "ru": "Russian", "es": "Spanish"}

_SYSTEM_RULES = (
    "You are a US tax assistant for visa holders and 1099 freelancers. "
    "Explain the provided deterministic numbers clearly without inventing new math. "
    "Do not recommend or criticize specific commercial tax software or tax preparation "
    "companies by name; if relevant, say neutrally that the user should check that their "
    "software or preparer supports Form 1040-NR. "
    "Never show raw status codes such as RESIDENT_ALIEN, NONRESIDENT_ALIEN or DUAL_STATUS_ALIEN; "
    "say 'resident for tax purposes', 'nonresident' or 'dual-status' in the answer language. "
)


def _language_instruction(language: str) -> str:
    return (
        f"Answer strictly in {_LANGUAGE_NAMES[language]}. If the user's latest message is written "
        "in another language, answer in the language of that latest message instead. Keep all "
        "suggested replies in the same language as the answer and do not mix languages."
    )


def _detect_language(text: str, default: str) -> str:
    if re.search(r"[а-яё]", text, re.IGNORECASE):
        return "ru"
    if re.search(r"[¿¡áéíóúñ]", text, re.IGNORECASE) or re.search(
        r"\b(hola|gracias|cómo|qué|soy|estoy|tengo|puedo|ayuda|por favor|"
        r"buenos|buenas|necesito|quiero|ingresos|impuestos|residente|estudiante)\b",
        text,
        re.IGNORECASE,
    ):
        return "es"
    if re.search(
        r"\b(hi|hello|hey|how|what|when|why|which|who|is|are|the|you|my|i'm|thanks|tax|taxes)\b",
        text,
        re.IGNORECASE,
    ):
        return "en"
    return default


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


LLM_MAX_OUTPUT_TOKENS = 1024


def _complete_text(text: Optional[str]) -> Optional[str]:
    """Returns stripped text, or None for an empty answer."""
    if not isinstance(text, str):
        return None
    text = text.strip()
    return text or None


def _call_chat_completions(
    url: str,
    api_key: str,
    model: str,
    prompt: str,
    language: str,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": _SYSTEM_RULES + _language_instruction(language),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": LLM_MAX_OUTPUT_TOKENS,
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
                choice = data["choices"][0]
                # A response cut by the token limit is never shown; the caller falls back.
                if choice.get("finish_reason") == "length":
                    return None
                return _complete_text(choice["message"].get("content"))
        except urllib.error.HTTPError as err:
            if err.code == 429 and attempt == 0:
                time.sleep(0.35 + random.uniform(0.05, 0.2))
                continue
            break
        except Exception:
            break
    return None


def call_llm(prompt: str, language: str = "en") -> Tuple[Optional[str], str]:
    language = normalize_language(language)
    digest = hashlib.sha256(f"{language}\0{prompt}".encode("utf-8")).hexdigest()
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
            text = _call_chat_completions(endpoint, key, model, prompt, language, headers)
            if text:
                res = (text, f"{label}:{model}")
                _CACHE[digest] = res
                return res

    for key in _get_keys("GEMINI_API_KEY"):
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
            body = {
                "contents": [{"parts": [{"text": f"{_SYSTEM_RULES}{_language_instruction(language)}\n\n{prompt}"}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "maxOutputTokens": LLM_MAX_OUTPUT_TOKENS,
                    # gemini-2.5-flash "thinks" by default and that budget is taken from
                    # maxOutputTokens, which cut answers mid-sentence. Disable thinking.
                    "thinkingConfig": {"thinkingBudget": 0},
                },
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                candidate = data["candidates"][0]
                if candidate.get("finishReason") not in (None, "STOP"):
                    continue  # MAX_TOKENS, SAFETY, ...: never show a partial answer
                parts = candidate.get("content", {}).get("parts", [])
                text = _complete_text("".join(p.get("text", "") for p in parts))
                if not text:
                    continue
                res = (text, "gemini:gemini-2.5-flash")
                _CACHE[digest] = res
                return res
        except Exception:
            continue

    return None, "deterministic-irs-explainer"


def generate_explanation(req: ExplainRequest) -> Dict[str, Any]:
    lang = normalize_language(req.language)
    reply_language = _detect_language(req.user_question or "", lang)
    res = req.residency_result or {}
    tax = req.tax_result or {}

    prompt = (
        f"{_language_instruction(lang)} Explain these US tax results in 3-5 short bullet points "
        f"(residency status & day count, tax liability & deduction savings, forms & deadlines). "
        f"Every sentence must be complete; do not stop mid-sentence.\n"
        f"Residency: {json.dumps(res, ensure_ascii=False)}\n"
        f"Taxes: {json.dumps(tax, ensure_ascii=False)}\n"
        f"Question: {req.user_question or 'None'}"
    )

    text, provider = call_llm(prompt, lang)
    if not text:
        status_code = res.get("residency_status", tax.get("residency_status", "RESIDENT_ALIEN"))
        status = status_text(reply_language, status_code, short=True) or res.get("status_label", "")
        w_days = res.get("total_weighted_days", 0)
        c_days = res.get("current_year_countable_days", 0)
        tot_tax = tax.get("total_tax_liability", 0.0)
        saved = tax.get("Deduction_tax_savings_usd", 0.0)
        fica_ref = tax.get("erroneous_fica_refund_amount", 0.0)

        parts = [
            tr(
                reply_language,
                "explain_residency",
                status=status,
                countable=c_days,
                weighted=w_days,
            )
        ]
        if tax:
            msg = tr(reply_language, "explain_tax", tax=tot_tax, saved=saved)
            if fica_ref > 0:
                msg += tr(reply_language, "explain_fica", amount=fica_ref)
            parts.append(msg)
        parts.append(tr(reply_language, "explain_next"))
        text = "\n\n".join(parts)

    return {
        "provider": provider,
        "language": reply_language,
        "explanation_markdown": humanize_codes(text, reply_language),
        "disclaimer": tr(reply_language, "explain_disclaimer"),
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


_STATUS_CODES = ("NONRESIDENT_ALIEN", "DUAL_STATUS_ALIEN", "RESIDENT_ALIEN")


def status_text(language: str, status: Optional[str], short: bool = False) -> str:
    """Human wording for a residency status code; raw codes are never shown to users."""
    if status not in _STATUS_CODES:
        return ""
    return tr(language, f"status_short_{status}" if short else f"status_{status}")


def humanize_codes(text: str, language: str) -> str:
    """Replace any raw status code an LLM may echo with its human wording."""
    for code in _STATUS_CODES:  # NONRESIDENT/DUAL first so RESIDENT_ALIEN doesn't match inside them
        text = re.sub(rf"\b{code}\b", status_text(language, code, short=True), text)
    return text


# ---------------------------------------------------------------------------
# Message analysis (deterministic): split into statement / question clauses.
# ---------------------------------------------------------------------------

_QUESTION_START = re.compile(
    r"^(?:(?:and|but|so|also|а|и|но|ну|y|pero|entonces)\s+)?"
    r"(?:what|what's|whats|how|why|when|where|which|who|whom|do|does|did|is|are|am|can|could|"
    r"should|would|will|tell me|explain|"
    r"что|чем|как|почему|зачем|когда|где|какой|какая|какое|какие|какую|каким|кто|сколько|"
    r"нужно ли|нужна ли|нужен ли|надо ли|можно ли|должен ли|в ч[её]м|объясни|расскажи|"
    r"qu[eé]|c[oó]mo|por qu[eé]|cu[aá]ndo|d[oó]nde|cu[aá]l|cu[aá]les|qui[eé]n|cu[aá]nto|"
    r"puedo|debo|tengo que|explica|expl[ií]came)\b",
    re.IGNORECASE,
)
_CLAUSE_SPLIT = re.compile(r"((?<!\d)\.(?!\d)|[!?;\n]+|,(?!\d))")

_SMALL_TALK = {
    "greeting": re.compile(
        r"^\W*(hi|hello|hey|hiya|good (morning|afternoon|evening)|привет|здравствуй\w*|добр\w+ (день|утро|вечер)|хай|"
        r"hola|buen[oa]s( d[ií]as| tardes| noches)?)\b",
        re.IGNORECASE,
    ),
    "how": re.compile(
        r"how are (you|u)|how's it going|how do you do|как (у )?(тебя |вас )?дела|как поживаешь|как ты\b|"
        r"c[oó]mo est[aá]s|c[oó]mo est[aá] usted|qu[eé] tal",
        re.IGNORECASE,
    ),
    "thanks": re.compile(r"\b(thanks|thank you|thx|ty)\b|спасибо|благодар|\bgracias\b", re.IGNORECASE),
    "who": re.compile(
        r"who are you|what are you|what can you do|кто ты|кто вы|что ты умеешь|что вы умеете|"
        r"qui[eé]n eres|qu[eé] eres|qu[eé] puedes hacer",
        re.IGNORECASE,
    ),
    "joke": re.compile(r"\bjoke\b|шутк|анекдот|\bchiste\b", re.IGNORECASE),
}
_OFF_TOPIC = re.compile(
    r"weather|forecast|recipe|cook|football|soccer|basketball|movie|film|music|song|python|javascript|"
    r"write (me )?code|bitcoin|crypto|horoscope|погод|прогноз|рецепт|приготов|футбол|фильм|кино|музык|песн|"
    r"напиши код|гороскоп|биткоин|clima|qu[eé] tiempo hace|receta|cocinar|f[uú]tbol|pel[ií]cula|m[uú]sica|"
    r"canci[oó]n|hor[oó]scopo",
    re.IGNORECASE,
)
_TAX_WORDS = re.compile(
    r"tax|irs|visa|form|refund|deduct|income|wage|resident|налог|виз|форм|возврат|вычет|доход|зарплат|резидент|"
    r"impuest|formulario|reembolso|deducci|ingreso|salario|residen",
    re.IGNORECASE,
)


def _split_clauses(message: str) -> Tuple[List[str], List[str]]:
    """Returns (statement clauses, question clauses)."""
    parts = _CLAUSE_SPLIT.split(message)
    statements: List[str] = []
    questions: List[str] = []
    for i in range(0, len(parts), 2):
        clause = parts[i].strip().lstrip("¿¡").strip()
        if not clause:
            continue
        delimiter = parts[i + 1] if i + 1 < len(parts) else ""
        if "?" in delimiter or _QUESTION_START.match(clause):
            questions.append(clause)
        else:
            statements.append(clause)
    return statements, questions


def _analyze_message(message: str) -> Dict[str, Any]:
    statements, questions = _split_clauses(message)
    small_talk = [kind for kind, pattern in _SMALL_TALK.items() if pattern.search(message)]
    # FAQ topics come from question clauses; a bare keyword message ("FICA") also counts.
    faq_text = " ".join(questions) or (message if not small_talk else "")
    topics = faq.find_topics(faq_text) if faq_text else []
    off_topic = bool(_OFF_TOPIC.search(message)) and not topics
    if questions and not topics and not small_talk and not _TAX_WORDS.search(" ".join(questions)):
        off_topic = True
    return {
        "statements": statements,
        "questions": questions,
        "small_talk": small_talk,
        "topics": topics,
        "off_topic": off_topic,
    }


_PROFILE_FIELDS = (
    "visa_type",
    "entry_date",
    "country_of_citizenship",
    "gross_1099_income",
    "business_deductions",
    "w2_wages",
    "w2_federal_withheld",
    "w2_fica_withheld",
)


def _extract_from_statements(statements: List[str], profile: CollectedTaxProfile) -> Dict[str, Any]:
    """Only statement clauses can fill profile fields; questions and small talk never do."""
    if not statements:
        return {}
    before = dump_model(profile)
    candidate = _extract_slots(" . ".join(statements), CollectedTaxProfile(**before))
    after = dump_model(candidate)
    return {k: after[k] for k in _PROFILE_FIELDS if after[k] != before[k]}


# ---------------------------------------------------------------------------
# LLM mode: structured JSON answer, validated before it touches the profile.
# ---------------------------------------------------------------------------

_CHAT_JSON_RULES = (
    "Classify the user's latest message and answer it. Rules:\n"
    "- intent is one of: answer (the user answers a profile question), tax_question (US tax / visa question), "
    "small_talk (greeting, how are you, thanks, who are you, joke), off_topic (not about US taxes). "
    "A message can both answer and ask; then use tax_question and still extract the fields.\n"
    "- Always reply to what the user actually said first: answer tax questions in 2-5 sentences using the "
    "profile and calculated results, cite official IRS pages (irs.gov) when useful, never invent numbers or "
    "dates that are not in the provided data; for small talk reply with one friendly sentence; for off-topic "
    "say politely you only help with US taxes and tax residency.\n"
    "- extracted_fields: ONLY values the user explicitly stated in the latest message (keys: visa_type, "
    "entry_date as YYYY-MM-DD, country_of_citizenship, gross_1099_income, business_deductions, w2_wages, "
    "w2_federal_withheld, w2_fica_withheld). Never guess. Empty object if nothing was stated.\n"
    "- next_question: if profile fields are still missing after extraction, one short question for the next "
    "missing field, phrased differently from the previous assistant message; otherwise empty string.\n"
    "- Never output raw codes like RESIDENT_ALIEN or NONRESIDENT_ALIEN; use plain words.\n"
    "- suggested_replies: 2-3 short replies the user might send next.\n"
    'Return ONLY a JSON object: {"intent": "...", "reply": "...", "extracted_fields": {}, '
    '"next_question": "...", "suggested_replies": []}'
)
_INTENTS = {"answer", "tax_question", "small_talk", "off_topic"}


def _parse_json_object(text: str) -> Optional[Dict[str, Any]]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _number_evidence(value: float, message: str) -> bool:
    digits = re.sub(r"[,\s]", "", message.lower())
    plain = f"{value:.2f}".rstrip("0").rstrip(".")
    if plain in digits:
        return True
    if value >= 1000 and value % 1000 == 0 and re.search(rf"\b{int(value // 1000)}\s*(k|к|тыс)", message.lower()):
        return True
    return value == 0 and bool(re.search(r"\b0\b|no income|нет дохода|sin ingresos|no expenses|нет расходов", message.lower()))


def _validated_fields(raw: Any, message: str) -> Dict[str, Any]:
    """Keep only well-typed fields that are actually present in the user's message."""
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, Any] = {}
    low = message.lower()
    for key, value in raw.items():
        if key not in _PROFILE_FIELDS or value in (None, ""):
            continue
        if key in ("visa_type", "country_of_citizenship"):
            if isinstance(value, str) and re.sub(r"[^a-z0-9]", "", value.lower())[:3] in re.sub(r"[^a-z0-9а-яё]", "", low):
                out[key] = value.strip()
        elif key == "entry_date":
            if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) and value[:4] in message:
                out[key] = value
        else:
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if number >= 0 and _number_evidence(number, message):
                out[key] = number
    return out


# ---------------------------------------------------------------------------
# Deterministic reply building.
# ---------------------------------------------------------------------------


def _next_question_key(missing: List[str]) -> Optional[str]:
    for field, key in (
        ("visa_type", "visa"),
        ("entry_date", "entry"),
        ("income_sources", "income"),
        ("business_deductions", "deductions"),
    ):
        if field in missing:
            return key
    return None


def _question_variants(
    language: str, key: str, profile: CollectedTaxProfile, status: Optional[str], with_ack: bool
) -> List[str]:
    values = {
        "visa": profile.visa_type or "",
        "income": profile.gross_1099_income or 0.0,
        "status": status_text(language, status) or status_text(language, "NONRESIDENT_ALIEN"),
    }
    variants = [tr(language, f"chat_q_{key}_{i}", **values) for i in (1, 2, 3)]
    if with_ack:
        # The original acknowledging phrasings come first right after the user answered a question.
        legacy = {
            "visa": tr(language, "chat_ask_visa"),
            "entry": tr(language, "chat_ask_entry", visa=values["visa"]),
            "income": tr(language, "chat_ask_income", status=values["status"]),
            "deductions": tr(language, "chat_ask_deductions", income=values["income"]),
        }[key]
        variants.insert(0, legacy)
    return variants


def _pick_fresh(variants: List[str], previous_reply: str) -> str:
    """First phrasing that the previous assistant message did not already use."""
    for variant in variants:
        if variant not in previous_reply:
            return variant
    return variants[-1]


def _chips(language: str, missing: List[str]) -> List[str]:
    if "visa_type" in missing:
        return [tr(language, f"chat_visa_{i}") for i in range(1, 6)]
    if "entry_date" in missing:
        return [tr(language, f"chat_entry_{i}") for i in range(1, 4)]
    if "income_sources" in missing:
        return [tr(language, f"chat_income_{i}") for i in range(1, 4)]
    if "business_deductions" in missing:
        return [tr(language, f"chat_deduction_{i}") for i in range(1, 4)]
    return [tr(language, f"chat_complete_{i}") for i in range(1, 4)]


def _small_talk_reply(language: str, kinds: List[str]) -> str:
    order = ["greeting", "how", "thanks", "who", "joke"]
    picked = [k for k in order if k in kinds]
    if "how" in picked and "greeting" in picked:
        picked.remove("greeting")
        return f"{tr(language, 'smalltalk_greeting')} {' '.join(tr(language, f'smalltalk_{k}') for k in picked)}"
    return " ".join(tr(language, f"smalltalk_{k}") for k in picked)


def _missing_fields(profile: CollectedTaxProfile) -> List[str]:
    missing: List[str] = []
    if not profile.visa_type:
        missing.append("visa_type")
    if not profile.entry_date:
        missing.append("entry_date")
    if profile.gross_1099_income is None and profile.w2_wages is None:
        missing.append("income_sources")
    if profile.gross_1099_income and profile.gross_1099_income > 0 and profile.business_deductions is None:
        missing.append("business_deductions")
    return missing


def _live_calculation(profile: CollectedTaxProfile, lang: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    live_res: Optional[Dict[str, Any]] = None
    live_tax: Optional[Dict[str, Any]] = None
    if not profile.visa_type:
        return live_res, live_tax
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
            language=lang,
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
                language=lang,
            )
        )
        live_tax = dump_model(tax_obj)
    return live_res, live_tax


def run_chat_turn(req: ChatAgentRequest) -> Dict[str, Any]:
    lang = normalize_language(req.language)
    profile = req.collected_profile or CollectedTaxProfile()
    user_messages = [m.content for m in req.messages if m.role == "user"]
    last_msg = user_messages[-1] if user_messages else ""
    previous_reply = next((m.content for m in reversed(req.messages) if m.role == "assistant"), "")
    reply_language = _detect_language(last_msg, lang)
    analysis = _analyze_message(last_msg)

    # ---- 1. Try the LLM (structured JSON). Its fields are validated against the message text.
    missing_before = _missing_fields(profile)
    live_res_before, live_tax_before = _live_calculation(profile, lang)
    prompt = (
        f"You are ARATax AI. {_language_instruction(reply_language)}\n{_CHAT_JSON_RULES}\n"
        f"Previous assistant message: {previous_reply}\n"
        f"User message: {last_msg}\n"
        f"Profile so far: {json.dumps(dump_model(profile), ensure_ascii=False)}\n"
        f"Missing fields: {missing_before}\n"
        f"Calculated residency: {json.dumps(live_res_before, ensure_ascii=False)}\n"
        f"Calculated taxes: {json.dumps(live_tax_before, ensure_ascii=False)}"
    )
    raw_reply, provider = call_llm(prompt, lang)
    llm = _parse_json_object(raw_reply) if raw_reply else None
    if llm and isinstance(llm.get("reply"), str) and llm["reply"].strip():
        intent = llm.get("intent") if llm.get("intent") in _INTENTS else "tax_question"
        extracted = _validated_fields(llm.get("extracted_fields"), last_msg)
    else:
        llm = None
        if raw_reply:
            provider = "deterministic-fallback"
        extracted = _extract_from_statements(analysis["statements"], profile)
        if extracted and not analysis["questions"]:
            analysis["topics"] = []  # "I paid $3,000 FICA" is an answer, not a FICA question
        intent = (
            "tax_question" if analysis["topics"]
            else "small_talk" if analysis["small_talk"]
            else "off_topic" if analysis["off_topic"]
            else "answer" if extracted
            else "unknown"
        )

    for key, value in extracted.items():
        setattr(profile, key, value)

    missing = _missing_fields(profile)
    is_complete = not missing
    live_res, live_tax = _live_calculation(profile, lang)
    status = (live_res or {}).get("residency_status")
    question_key = _next_question_key(missing)

    # ---- 2. Build the reply: answer what was said first, then return to the questionnaire.
    if llm:
        parts = [humanize_codes(llm["reply"].strip(), reply_language)]
        if not is_complete:
            llm_question = llm.get("next_question") if isinstance(llm.get("next_question"), str) else ""
            question = humanize_codes(llm_question.strip(), reply_language) or _pick_fresh(
                _question_variants(reply_language, question_key, profile, status, with_ack=False), previous_reply
            )
            if question not in parts[0]:
                parts.append(question)
        elif intent != "answer":
            parts.append(tr(reply_language, "chat_complete_hint"))
        chips = llm.get("suggested_replies")
        if not (isinstance(chips, list) and chips and all(isinstance(c, str) for c in chips)):
            chips = _chips(reply_language, missing)
        chips = chips[:5]
    else:
        only_answer = intent == "answer"
        parts = []
        if analysis["small_talk"]:
            parts.append(_small_talk_reply(reply_language, analysis["small_talk"]))
        for topic in analysis["topics"][:1]:
            parts.append(
                faq.answer(topic, reply_language, profile.tax_year, status, status_text(reply_language, status))
            )
        if analysis["off_topic"]:
            parts.append(tr(reply_language, "chat_off_topic"))
        if intent == "unknown":
            parts.append(tr(reply_language, "chat_unknown"))
        if extracted and not only_answer:
            parts.append(tr(reply_language, "chat_saved"))

        if is_complete:
            if only_answer or not parts:
                tot = live_tax["total_tax_liability"] if live_tax else 0.0
                saved = live_tax["Deduction_tax_savings_usd"] if live_tax else 0.0
                parts.append(
                    tr(reply_language, "chat_done", status=status_text(reply_language, status), tax=tot, saved=saved)
                )
            else:
                parts.append(tr(reply_language, "chat_complete_hint"))
        else:
            variants = _question_variants(reply_language, question_key, profile, status, with_ack=only_answer)
            question = _pick_fresh(variants, previous_reply)
            if analysis["topics"] or analysis["off_topic"]:
                question = f"{tr(reply_language, 'chat_transition')} {question}"
            parts.append(question)
        chips = _chips(reply_language, missing)

    reply = "\n\n".join(p for p in parts if p)

    return {
        "reply": reply,
        "provider": provider,
        "intent": intent,
        "collected_profile": dump_model(profile),
        "missing_fields": missing,
        "is_complete": is_complete,
        "suggested_replies": chips,
        "live_calculation": {
            "residency": live_res,
            "taxes": live_tax,
            "form_8843_ready": bool(live_res and live_res.get("exempt_individual_active")),
        },
    }
