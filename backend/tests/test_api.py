from fastapi.testclient import TestClient
from app.main import app
client=TestClient(app)
def test_health(): assert client.get("/health").status_code==200
def test_validation(): assert client.post("/api/validate",json={"xyz":"2\nHydrogen\nH 0 0 0\nH 0 0 0.74"}).json()["valid"]
def test_reject_bad_xyz(): assert client.post("/api/validate",json={"xyz":"hello world"}).status_code==422
def test_public_jobs_disabled(monkeypatch):
    monkeypatch.delenv("ORBIXA_ENABLE_JOBS",raising=False)
    assert client.post("/api/jobs",json={"xyz":"2\nHydrogen\nH 0 0 0\nH 0 0 0.74"}).status_code==503

def test_reject_colliding_atoms():
    payload={"xyz":"2\nCollision\nH 0 0 0\nH 0 0 0"}
    assert client.post("/api/validate",json=payload).status_code==422

def test_reject_odd_electron_restricted():
    payload={"xyz":"1\nHydrogen\nH 0 0 0"}
    assert client.post("/api/validate",json=payload).status_code==422

def test_accept_open_shell_uhf():
    payload={"xyz":"1\nHydrogen\nH 0 0 0","method":"UHF","spin":1}
    assert client.post("/api/validate",json=payload).status_code==200

def test_missing_job():
    assert client.get("/api/jobs/not-a-job").status_code==404
