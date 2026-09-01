from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

import backend.web.app as webapp
from backend.web.app import create_app


def test_health(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(webapp, "JOBS_DIR", tmp_path / "jobs")
    client = TestClient(create_app())
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_index_renders_upload_copy(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(webapp, "JOBS_DIR", tmp_path / "jobs")
    client = TestClient(create_app())
    response = client.get("/")
    assert response.status_code == 200
    assert "Data QA Agent" in response.text
    assert "Drop a CSV or Excel file" in response.text


def test_rejects_non_spreadsheet(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(webapp, "JOBS_DIR", tmp_path / "jobs")
    client = TestClient(create_app())
    response = client.post("/api/jobs", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code == 400


def _wait(client: TestClient, job_id: str) -> dict:
    job = {}
    for _ in range(80):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job.get("state") in {"done", "error"}:
            return job
        time.sleep(0.15)
    return job


def test_upload_sample_pos_returns_pdf(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(webapp, "JOBS_DIR", tmp_path / "jobs")
    client = TestClient(create_app())
    source = Path("backend/data/raw/sample_pos.csv")
    response = client.post(
        "/api/jobs",
        files={"file": (source.name, source.read_bytes(), "text/csv")},
    )
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    job = _wait(client, job_id)
    assert job.get("state") == "done", job
    assert job["result"]["analysis_ready"] is True
    pdf = client.get(f"/api/jobs/{job_id}/pdf")
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF"
    clean = client.get(f"/api/jobs/{job_id}/clean")
    assert clean.status_code == 200
    assert b"sales_value" in clean.content
