from fastapi.testclient import TestClient
from app.main import app
client=TestClient(app)
def test_health(): assert client.get("/health").status_code==200
def test_validation(): assert client.post("/api/validate",json={"xyz":"2\nHydrogen\nH 0 0 0\nH 0 0 0.74"}).json()["valid"]
def test_reject_bad_xyz(): assert client.post("/api/validate",json={"xyz":"hello world"}).status_code==422
def test_public_jobs_disabled(monkeypatch):
    monkeypatch.delenv("ORBIXA_ENABLE_JOBS",raising=False)
    assert client.post("/api/jobs",json={"xyz":"2\nHydrogen\nH 0 0 0\nH 0 0 0.74"}).status_code==503
