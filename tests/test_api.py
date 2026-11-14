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


if __name__ == "__main__":
    test_health_and_presets()
    test_analyze_all_and_pdf()
    test_chat_flow()
    print("OK")
