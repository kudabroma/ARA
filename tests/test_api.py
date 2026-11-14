import sys
from pathlib import Path

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


if __name__ == "__main__":
    test_health_and_presets()
    test_analyze_all_and_pdf()
    test_chat_flow()
    print("OK")
