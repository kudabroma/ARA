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


if __name__ == "__main__":
    test_health_and_presets()
    test_analyze_all_and_pdf()
    test_chat_flow()
    print("OK")
