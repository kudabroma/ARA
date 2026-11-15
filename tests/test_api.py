import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_and_presets():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["subscription"]["active"] is True

    presets = client.get("/api/demo-presets")
    assert presets.status_code == 200
    assert presets.json()["count"] == 3


def test_demo_presets_localize_titles_but_not_payload():
    by_lang = {
        lang: client.get("/api/demo-presets", params={"language": lang}).json()["presets"]
        for lang in ("en", "ru", "es")
    }
    assert client.get("/api/demo-presets").json()["presets"] == by_lang["en"]
    for i in range(3):
        payloads = {lang: presets[i]["payload"] for lang, presets in by_lang.items()}
        assert payloads["en"] == payloads["ru"] == payloads["es"]
        titles = {presets[i]["title"] for presets in by_lang.values()}
        assert len(titles) == 3
    assert by_lang["ru"][0]["title"] == "Выпускник F-1 OPT: W-2 + фриланс 1099, возврат FICA $3,442"
    for presets in by_lang.values():
        assert "F-1 OPT" in presets[0]["title"] and "$3,442" in presets[0]["title"]


def test_nonresident_texts_are_brand_neutral_and_india_warning_is_conditional():
    import json as _json

    for lang in ("en", "ru", "es"):
        presets = client.get("/api/demo-presets", params={"language": lang}).json()["presets"]
        for preset in presets:
            data = client.post("/api/analyze-all", json={**preset["payload"], "language": lang}).json()
            dumped = _json.dumps(data, ensure_ascii=False)
            for brand in ("TurboTax", "FreeTaxUSA", "TaxSlayer", "H&R Block"):
                assert brand not in dumped

    def warnings(country):
        res = client.post(
            "/api/analyze-all",
            json={
                "residency": {
                    "tax_year": 2025,
                    "stays": [{"visa_type": "F-1", "entry_date": "2024-08-20"}],
                    "country_of_citizenship": country,
                }
            },
        ).json()["residency"]
        assert res["residency_status"] == "NONRESIDENT_ALIEN"
        return " ".join(res["software_warnings"])

    assert "India" in warnings("India")
    assert "India" not in warnings("Kazakhstan")
    assert "generally cannot claim the standard deduction" in warnings("Kazakhstan")


def test_default_tax_year_is_2026_everywhere():
    from app.schemas import (
        CollectedTaxProfile, Form8843Request, ResidencyRequest, TaxCalculationRequest, TransactionsAnalyzeRequest,
    )

    for model in (ResidencyRequest, TaxCalculationRequest, TransactionsAnalyzeRequest, CollectedTaxProfile):
        assert model().tax_year == 2026
    assert Form8843Request().tax_year == 2026
    res = client.post("/api/analyze-all", json={"residency": {"stays": [{"visa_type": "H-1B", "entry_date": "2026-01-01"}]}})
    assert res.json()["residency"]["tax_year"] == 2026
    # 2025 is still accepted when asked for explicitly
    res = client.post("/api/analyze-all", json={"residency": {"tax_year": 2025, "stays": []}})
    assert res.json()["residency"]["tax_year"] == 2025


def test_demo_presets_are_2026_and_keep_their_conclusions():
    presets = {p["preset_id"]: p["payload"] for p in client.get("/api/demo-presets").json()["presets"]}
    results = {pid: client.post("/api/analyze-all", json=payload).json() for pid, payload in presets.items()}
    for data in results.values():
        assert data["residency"]["tax_year"] == 2026
        assert data["taxes"]["tax_year"] == 2026

    case1 = results["f1_opt_hybrid_1099_fica"]
    assert case1["residency"]["residency_status"] == "NONRESIDENT_ALIEN"
    assert case1["taxes"]["erroneous_fica_refund_amount"] > 0
    assert case1["form_8843"]["pdf_base64"].startswith("JVBERi")

    case2 = results["opt_to_h1b_october_transition"]
    assert case2["residency"]["residency_status"] == "NONRESIDENT_ALIEN"
    assert case2["residency"]["current_year_countable_days"] == 92  # H-1B from Oct 1, 2026
    assert case2["residency"]["first_year_choice_available"] is True
    assert case2["form_8843"]["pdf_base64"].startswith("JVBERi")  # demo profile -> PDF right away

    case3 = results["digital_nomad_1099_contractor"]
    assert case3["residency"]["residency_status"] == "RESIDENT_ALIEN"
    assert case3["taxes"]["self_employment_tax"] > 0


def test_analyze_all_and_pdf():
    preset = client.get("/api/demo-presets").json()["presets"][0]["payload"]
    res = client.post("/api/analyze-all", json=preset)
    assert res.status_code == 200
    data = res.json()
    assert data["residency"]["residency_status"] == "NONRESIDENT_ALIEN"
    assert data["taxes"]["erroneous_fica_refund_amount"] == 3442.50
    assert data["form_8843"]["pdf_base64"].startswith("JVBERi")


def test_chat_flow():
    r1 = client.post("/api/chat", json={
        "language": "ru",
        "messages": [{"role": "user", "content": "Я в США по F-1 OPT с августа 2023"}]
    })
    assert r1.status_code == 200
    p1 = r1.json()["collected_profile"]
    assert p1["visa_type"] == "OPT"

    r2 = client.post("/api/chat", json={
        "language": "ru",
        "collected_profile": p1,
        "messages": [
            {"role": "user", "content": "Я в США по F-1 OPT с августа 2023"},
            {"role": "user", "content": "Заработал $28000 по 1099 и расходы $4500"}
        ]
    })
    assert r2.status_code == 200
    assert r2.json()["is_complete"] is True


def test_analyze_all_defaults_empty_exit_to_tax_year_end():
    res = client.post(
        "/api/analyze-all",
        json={
            "residency": {
                "tax_year": 2025,
                "stays": [{"visa_type": "H-1B", "entry_date": "2025-01-01"}],
            }
        },
    )
    assert res.status_code == 200
    current_year = next(row for row in res.json()["residency"]["year_breakdown"] if row["year"] == 2025)
    assert current_year["total_physical_days"] == 365


def test_analyze_all_treats_null_fields_as_defaults():
    res = client.post(
        "/api/analyze-all",
        json={
            "residency": {
                "tax_year": 2025,
                "stays": [{"visa_type": "OPT", "entry_date": "2023-08-15"}],
                "country_of_citizenship": None,
            },
            "taxes": {
                "tax_year": 2025,
                "visa_type": "OPT",
                "country_of_citizenship": None,
                "gross_1099_income": 28000,
                "business_deductions": 4500,
                "w2_wages": None,
                "w2_federal_withheld": None,
                "w2_fica_withheld": None,
            },
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["taxes"]["w2_federal_withheld"] == 0


def test_analyze_all_rejects_invalid_stay_dates():
    for field in ("entry_date", "exit_date"):
        stay = {
            "visa_type": "H-1B",
            "entry_date": "2025-01-01",
            "exit_date": "2025-12-31",
        }
        stay[field] = "2025-02-30"
        res = client.post(
            "/api/analyze-all",
            json={"residency": {"tax_year": 2025, "stays": [stay]}},
        )
        assert res.status_code == 422


def test_chat_maps_invalid_profile_date_to_bad_request():
    res = client.post(
        "/api/chat",
        json={
            "messages": [{"role": "user", "content": "I am on F-1"}],
            "collected_profile": {"visa_type": "F-1", "entry_date": "2025-02-30"},
        },
    )
    assert res.status_code == 400


def test_language_changes_text_without_changing_numeric_results(monkeypatch):
    monkeypatch.setattr(
        "app.services.advisor.call_llm",
        lambda prompt, language="en": (None, "deterministic-irs-explainer"),
    )
    payload = client.get("/api/demo-presets").json()["presets"][0]["payload"]

    def numeric_values(value):
        if isinstance(value, bool):
            return []
        if isinstance(value, (int, float)):
            return [value]
        if isinstance(value, dict):
            return [number for item in value.values() for number in numeric_values(item)]
        if isinstance(value, list):
            return [number for item in value for number in numeric_values(item)]
        return []

    results = {}
    for language in ("en", "ru", "es"):
        response = client.post(
            "/api/analyze-all",
            json={**payload, "language": language},
        )
        assert response.status_code == 200
        results[language] = response.json()

    assert results["en"]["residency"]["status_label"] != results["ru"]["residency"]["status_label"]
    assert results["ru"]["residency"]["status_label"] != results["es"]["residency"]["status_label"]
    numbers = {language: numeric_values(result) for language, result in results.items()}
    assert numbers["en"] == numbers["ru"] == numbers["es"]


def test_chat_fallback_uses_latest_message_language(monkeypatch):
    monkeypatch.setattr(
        "app.services.advisor.call_llm",
        lambda prompt, language="en": (None, "deterministic-irs-explainer"),
    )
    spanish = client.post(
        "/api/chat",
        json={"language": "en", "messages": [{"role": "user", "content": "Hola, necesito ayuda"}]},
    ).json()
    russian = client.post(
        "/api/chat",
        json={"language": "es", "messages": [{"role": "user", "content": "Здравствуйте, нужна помощь"}]},
    ).json()

    assert "¿Qué visa" in spanish["reply"]
    assert "Estudiante" in spanish["suggested_replies"][0]
    assert "По какой визе" in russian["reply"]
    assert "Студенческая" in russian["suggested_replies"][0]


def test_explanation_fallback_localizes_to_question_language(monkeypatch):
    monkeypatch.setattr(
        "app.services.advisor.call_llm",
        lambda prompt, language="en": (None, "deterministic-irs-explainer"),
    )
    response = client.post(
        "/api/explain",
        json={"language": "en", "user_question": "Hola, ¿puedes explicarlo?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["language"] == "es"
    assert "Residencia fiscal" in data["explanation_markdown"]
    assert "Cálculo informativo" in data["disclaimer"]


class _FakeResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _fake_llm(monkeypatch, env_var, payload):
    from app.services import advisor

    sent = []

    def fake_urlopen(req, timeout=0):
        sent.append(json.loads(req.data.decode("utf-8")))
        return _FakeResponse(payload)

    for name in ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(env_var, "test-key")
    monkeypatch.setattr(advisor.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(advisor, "_CACHE", {})
    return sent


EXPLAIN_BODY = {
    "residency_result": {"residency_status": "NONRESIDENT_ALIEN", "current_year_countable_days": 92},
    "tax_result": {"total_tax_liability": 1542.0, "Deduction_tax_savings_usd": 700.0},
}


@pytest.mark.parametrize("language,marker", [("en", "Tax Residency"), ("ru", "Налоговый статус"), ("es", "Residencia fiscal")])
def test_explanation_cut_by_gemini_token_limit_uses_template(monkeypatch, language, marker):
    sent = _fake_llm(
        monkeypatch,
        "GEMINI_API_KEY",
        {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "**Residency Status & Day Count:** You are"}]}}]},
    )
    data = client.post("/api/explain", json={**EXPLAIN_BODY, "language": language}).json()
    assert data["provider"] == "deterministic-irs-explainer"
    assert "You are" not in data["explanation_markdown"]
    assert marker in data["explanation_markdown"]
    config = sent[0]["generationConfig"]
    assert config["maxOutputTokens"] >= 1024
    assert config["thinkingConfig"]["thinkingBudget"] == 0


def test_explanation_cut_by_openai_length_or_empty_uses_template(monkeypatch):
    sent = _fake_llm(
        monkeypatch,
        "OPENAI_API_KEY",
        {"choices": [{"finish_reason": "length", "message": {"content": "1. You are"}}]},
    )
    data = client.post("/api/explain", json={**EXPLAIN_BODY, "language": "en"}).json()
    assert data["provider"] == "deterministic-irs-explainer"
    assert sent[0]["max_tokens"] >= 1024

    _fake_llm(monkeypatch, "OPENAI_API_KEY", {"choices": [{"finish_reason": "stop", "message": {"content": "  "}}]})
    assert client.post("/api/explain", json=EXPLAIN_BODY).json()["provider"] == "deterministic-irs-explainer"


def test_complete_llm_explanation_is_returned_in_full(monkeypatch):
    full = "- You are a nonresident alien for 2025.\n- Your estimated tax is $1,542."
    sent = _fake_llm(
        monkeypatch,
        "GEMINI_API_KEY",
        {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": full}]}}]},
    )
    data = client.post("/api/explain", json=EXPLAIN_BODY).json()
    assert data["provider"] == "gemini:gemini-2.5-flash"
    assert data["explanation_markdown"] == full
    prompt = sent[0]["contents"][0]["parts"][0]["text"]
    assert "3-5 short bullet points" in prompt and "complete" in prompt
    assert "commercial tax software" in prompt


# ---------------------------------------------------------------------------
# Chat: answer any message first, then return to the questionnaire (fallback mode)
# ---------------------------------------------------------------------------

STATUS_CODES = ("RESIDENT_ALIEN", "NONRESIDENT_ALIEN", "DUAL_STATUS_ALIEN")
NEXT_VISA_QUESTION = {
    "en": ("visa or status", "visa"),
    "ru": ("визе", "виза"),
    "es": ("visa",),
}


@pytest.fixture
def no_llm(monkeypatch):
    monkeypatch.setattr(
        "app.services.advisor.call_llm",
        lambda prompt, language="en": (None, "deterministic-irs-explainer"),
    )


def _chat(text, language="en", profile=None, history=None):
    messages = list(history or []) + [{"role": "user", "content": text}]
    body = {"language": language, "messages": messages}
    if profile is not None:
        body["collected_profile"] = profile
    res = client.post("/api/chat", json=body)
    assert res.status_code == 200, res.text
    data = res.json()
    for code in STATUS_CODES:
        assert code not in data["reply"]
    return data


EMPTY_PROFILE_KEYS = ("visa_type", "entry_date", "gross_1099_income", "w2_wages", "business_deductions")


def _profile_unchanged(data, before=None):
    before = before or {}
    for key in EMPTY_PROFILE_KEYS:
        assert data["collected_profile"][key] == before.get(key)


@pytest.mark.parametrize(
    "text,ui_language,reply_language,friendly",
    [
        ("hey how are you?", "en", "en", "I'm doing great"),
        ("привет, как дела?", "en", "ru", "У меня всё отлично"),
        ("hola, ¿cómo estás?", "en", "es", "¡Muy bien"),
        ("hey how are you?", "ru", "en", "I'm doing great"),
    ],
)
def test_chat_small_talk_gets_friendly_reply_and_next_question(no_llm, text, ui_language, reply_language, friendly):
    data = _chat(text, ui_language)
    assert friendly in data["reply"]
    assert any(word in data["reply"] for word in NEXT_VISA_QUESTION[reply_language])
    assert data["intent"] == "small_talk"
    _profile_unchanged(data)
    assert data["missing_fields"][0] == "visa_type"


def test_chat_tax_question_is_answered_then_returns_to_questionnaire(no_llm):
    profile = {"visa_type": "OPT", "entry_date": "2023-08-15"}  # default tax year: 2026
    data = _chat("how to pay for taxes", profile=profile)
    assert "IRS Direct Pay" in data["reply"] and "1040-ES" in data["reply"]
    assert "April 15, 2027" in data["reply"]  # 2026 due dates come from app/config.py
    assert data["collected_profile"]["tax_year"] == 2026
    assert "Now, to calculate it precisely" in data["reply"]
    assert "how much did you earn" in data["reply"].split("\n\n")[-1].lower()
    assert data["intent"] == "tax_question"
    _profile_unchanged(data, profile)


@pytest.mark.parametrize(
    "text,language,expected",
    [
        ("what is the difference between 1040 and 1040-NR?", "en", ("Form 1040-NR", "nonresident")),
        ("в чём разница между 1040 и 1040-NR?", "ru", ("Form 1040-NR", "нерезидент")),
        ("¿cuál es la diferencia entre 1040 y 1040-NR?", "es", ("Form 1040-NR", "no residentes")),
    ],
)
def test_chat_explains_1040_vs_1040nr(no_llm, text, language, expected):
    data = _chat(text, "en")
    for fragment in expected:
        assert fragment in data["reply"]
    _profile_unchanged(data)


def test_chat_extracts_answer_and_answers_question_in_one_message(no_llm):
    data = _chat("I'm on F-1, what is FICA?")
    assert data["collected_profile"]["visa_type"] == "F-1"
    assert "Social Security" in data["reply"] and "Medicare" in data["reply"]
    assert "When did you first enter the US" in data["reply"] or "first arrive" in data["reply"] or "entry date" in data["reply"]


def test_chat_off_topic_is_declined_politely(no_llm):
    data = _chat("what's the weather?")
    assert "only help with US taxes" in data["reply"]
    assert any(word in data["reply"] for word in NEXT_VISA_QUESTION["en"])
    assert data["intent"] == "off_topic"
    _profile_unchanged(data)


def test_chat_unrecognised_message_asks_to_rephrase(no_llm):
    data = _chat("blorp zzz")
    assert "didn't quite get that" in data["reply"]
    _profile_unchanged(data)


def test_chat_does_not_repeat_the_same_question_twice_in_a_row(no_llm):
    first = _chat("what's the weather?")
    second = _chat(
        "what's the weather?",
        history=[
            {"role": "user", "content": "what's the weather?"},
            {"role": "assistant", "content": first["reply"]},
        ],
    )
    q1 = first["reply"].split("\n\n")[-1]
    q2 = second["reply"].split("\n\n")[-1]
    assert q1 != q2


def test_chat_status_is_never_shown_as_a_raw_code(no_llm):
    profile = {"tax_year": 2025, "visa_type": "H-1B", "entry_date": "2020-01-15"}
    for language in ("en", "ru", "es"):
        data = _chat("Am I a resident or nonresident?", language, profile=profile)
        assert data["live_calculation"]["residency"]["residency_status"] == "RESIDENT_ALIEN"
        done = _chat("$85,000 on W-2", language, profile=profile)
        assert done["is_complete"] is True
    explain = client.post(
        "/api/explain", json={"language": "ru", "residency_result": {"residency_status": "NONRESIDENT_ALIEN"}}
    ).json()
    for code in STATUS_CODES:
        assert code not in explain["explanation_markdown"]


def test_chat_llm_fields_must_be_stated_by_the_user(monkeypatch):
    llm_answer = json.dumps(
        {
            "intent": "tax_question",
            "reply": "FICA is Social Security plus Medicare. You are NONRESIDENT_ALIEN.",
            "extracted_fields": {"visa_type": "F-1", "w2_wages": 99999, "country_of_citizenship": "India"},
            "next_question": "",
            "suggested_replies": ["August 2023"],
        }
    )
    monkeypatch.setattr("app.services.advisor.call_llm", lambda prompt, language="en": (llm_answer, "test:model"))
    data = _chat("I'm on F-1, what is FICA?")
    assert data["provider"] == "test:model"
    assert data["collected_profile"]["visa_type"] == "F-1"
    assert data["collected_profile"]["w2_wages"] is None  # invented by the model -> dropped
    assert data["collected_profile"]["country_of_citizenship"] is None
    assert "Nonresident for tax purposes" in data["reply"]
    assert data["suggested_replies"] == ["August 2023"]


def _dialog(messages, language="ru"):
    history = [{"role": "assistant", "content": "Привет! Какая у вас виза и когда вы впервые въехали в США?"}]
    profile, replies, data = {}, [], None
    for text in messages:
        history.append({"role": "user", "content": text})
        data = _chat_raw(history, language, profile)
        profile = data["collected_profile"]
        replies.append(data["reply"])
        history.append({"role": "assistant", "content": data["reply"]})
    return data, replies


def _chat_raw(history, language, profile):
    res = client.post("/api/chat", json={"language": language, "messages": history, "collected_profile": profile})
    assert res.status_code == 200, res.text
    return res.json()


def test_chat_dialog_with_85000_on_1099_gives_a_real_tax(no_llm):
    data, replies = _dialog([
        "У меня виза F-1, въехал 1 сентября 2023 года.",
        "Да, у меня был доход по W-2.",
        "У меня также был доход по 1099.",
        "Только 1099: $85 000",
    ])
    profile = data["collected_profile"]
    assert profile["entry_date"] == "2023-09-01"
    assert profile["gross_1099_income"] == 85000
    assert profile["w2_wages"] == 0
    assert data["live_calculation"]["taxes"]["total_tax_liability"] > 0
    assert all("$0.00" not in r for r in replies)
    # "W-2 mentioned" and "also 1099" are understood as statements, not "didn't get that"
    assert "Не совсем понял" not in replies[1] and "W-2" in replies[1]
    assert "Понял, есть и 1099" in replies[2] and "1099" in replies[2] and "W-2" in replies[2]
    # F-1 (not OPT) + 1099: soft authorization note
    assert "DSO" in replies[3]

    # finishing the profile shows the summary built from the calculation
    data, replies = _dialog([
        "У меня виза F-1, въехал 1 сентября 2023 года.",
        "Только 1099: $85 000",
        "Расходов не было ($0)",
    ])
    assert data["is_complete"] is True
    done = replies[-1]
    assert "нерезидент (Form 1040-NR)" in done
    assert "доход по 1099 $85,000" in done
    tax = data["live_calculation"]["taxes"]["total_tax_liability"]
    assert f"${tax:,.0f}" in done and tax > 0
    assert data["collected_profile"]["no_income"] is None


def test_chat_never_completes_on_a_silent_zero(no_llm):
    data, _ = _dialog(["I'm on H-1B since 2020-01-15", "I had W-2 wages"], "en")
    assert data["is_complete"] is False
    assert "w2_wages" in data["missing_fields"]
    data, replies = _dialog(["I'm on H-1B since 2020-01-15", "$0 on W-2"], "en")
    assert data["is_complete"] is False and "income_sources" in data["missing_fields"]
    # an explicit "no income" is a valid answer
    data, replies = _dialog(["I'm on H-1B since 2020-01-15", "No income ($0)"], "en")
    assert data["is_complete"] is True
    assert "no income" in replies[-1]


@pytest.mark.parametrize("amount", ["$85 000", "85,000", "$85k", "85к", "85 тыс", "85 тысяч", "eighty-five thousand", "85 mil"])
def test_chat_reads_1099_amount_in_any_format(no_llm, amount):
    data, _ = _dialog(["I'm on OPT since 2024-08-20", f"1099 only: {amount}"], "en")
    assert data["collected_profile"]["gross_1099_income"] == 85000
    assert data["collected_profile"]["w2_wages"] == 0


def test_f1_with_1099_gets_an_advisory_in_results():
    body = {
        "residency": {"stays": [{"visa_type": "F-1", "entry_date": "2024-08-20"}]},
        "taxes": {"visa_type": "F-1", "gross_1099_income": 85000},
        "language": "ru",
    }
    data = client.post("/api/analyze-all", json=body).json()
    assert any("DSO" in a for a in data["advisories"])
    assert data["taxes"]["total_tax_liability"] > 0
    body["taxes"]["visa_type"] = "OPT"
    assert client.post("/api/analyze-all", json=body).json()["advisories"] == []


if __name__ == "__main__":
    test_health_and_presets()
    test_analyze_all_and_pdf()
    test_chat_flow()
    print("OK")
