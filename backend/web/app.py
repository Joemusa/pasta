"""FastAPI workspace: upload POS data → Data QA Agent → Report PDF."""

from __future__ import annotations

import json
import logging
import re
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from backend.pipeline import run_pipeline

logger = logging.getLogger("backend.web")

REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = Path(__file__).resolve().parent / "static"
JOBS_DIR = REPO_ROOT / "backend" / "data" / "jobs"
SAMPLE_POS = REPO_ROOT / "backend" / "data" / "raw" / "sample_pos.csv"
ALLOWED_SUFFIXES = {".csv", ".xlsx", ".xls"}
MAX_UPLOAD_BYTES = 40 * 1024 * 1024

_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()


def _safe_filename(name: str | None) -> str:
    raw = Path(name or "upload.csv").name
    cleaned = re.sub(r"[^A-Za-z0-9._ ()-]+", "_", raw).strip("._")
    return cleaned or "upload.csv"


def _job_dir(job_id: str) -> Path:
    return JOBS_DIR / job_id


def _set_job(job_id: str, **fields: object) -> None:
    with _LOCK:
        current = _JOBS.get(job_id, {"job_id": job_id})
        current.update(fields)
        _JOBS[job_id] = current
        meta = _job_dir(job_id) / "job.json"
        meta.parent.mkdir(parents=True, exist_ok=True)
        meta.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")


def _get_job(job_id: str) -> dict:
    with _LOCK:
        job = _JOBS.get(job_id)
    if job:
        return job
    meta = _job_dir(job_id) / "job.json"
    if meta.exists():
        return json.loads(meta.read_text(encoding="utf-8"))
    raise HTTPException(status_code=404, detail="Job not found")


def _run_job(job_id: str, source: Path) -> None:
    def on_stage(stage: str) -> None:
        _set_job(job_id, state="running", stage=stage)

    try:
        _set_job(job_id, state="running", stage="qa")
        result = run_pipeline(source, _job_dir(job_id), on_stage=on_stage)
        _set_job(
            job_id,
            state="done",
            stage="done",
            result=result.summary(),
            pdf_path=str(result.pdf_path),
            clean_path=str(result.clean_path) if result.clean_path else None,
            qa_json_path=str(result.qa_json_path) if result.qa_json_path else None,
            exclusions_path=str(result.exclusions_path) if result.exclusions_path else None,
        )
    except Exception as exc:
        logger.exception("job_failed job_id=%s", job_id)
        _set_job(job_id, state="error", stage="error", error=str(exc))


def _start_job(source: Path, original_name: str) -> str:
    job_id = uuid.uuid4().hex[:12]
    dest_dir = _job_dir(job_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    _set_job(job_id, state="queued", stage="upload", filename=original_name)
    thread = threading.Thread(target=_run_job, args=(job_id, source), daemon=True)
    thread.start()
    return job_id


def create_app() -> FastAPI:
    app = FastAPI(title="FMCG Commercial Intelligence", version="0.2.0")
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        return HTMLResponse(html)

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    @app.post("/api/jobs")
    async def create_job(file: UploadFile = File(...)) -> dict:
        filename = _safe_filename(file.filename)
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            raise HTTPException(status_code=400, detail="Upload a CSV or Excel file (.csv, .xlsx, .xls)")
        payload = await file.read()
        if not payload:
            raise HTTPException(status_code=400, detail="The file is empty")
        if len(payload) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=400, detail="File is larger than 40 MB")
        job_id = uuid.uuid4().hex[:12]
        dest_dir = _job_dir(job_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        source = dest_dir / filename
        source.write_bytes(payload)
        _set_job(job_id, state="queued", stage="upload", filename=filename)
        threading.Thread(target=_run_job, args=(job_id, source), daemon=True).start()
        return {"job_id": job_id, "filename": filename}

    @app.post("/api/jobs/sample")
    def create_sample_job() -> dict:
        if not SAMPLE_POS.exists():
            raise HTTPException(status_code=404, detail="Sample POS file is not in this checkout")
        job_id = _start_job(SAMPLE_POS, SAMPLE_POS.name)
        return {"job_id": job_id, "filename": SAMPLE_POS.name}

    @app.get("/api/jobs/{job_id}")
    def job_status(job_id: str) -> dict:
        return _get_job(job_id)

    def _file_response(job_id: str, key: str, download_name: str, media: str) -> FileResponse:
        job = _get_job(job_id)
        path_value = job.get(key)
        if job.get("state") != "done" or not path_value:
            raise HTTPException(status_code=404, detail="File is not ready")
        path = Path(str(path_value))
        if not path.exists():
            raise HTTPException(status_code=404, detail="File is not ready")
        return FileResponse(path, media_type=media, filename=download_name)

    @app.get("/api/jobs/{job_id}/pdf")
    def download_pdf(job_id: str) -> FileResponse:
        name = Path(str(_get_job(job_id).get("filename") or "report")).stem
        return _file_response(job_id, "pdf_path", f"{name}.report.pdf", "application/pdf")

    @app.get("/api/jobs/{job_id}/clean")
    def download_clean(job_id: str) -> FileResponse:
        name = Path(str(_get_job(job_id).get("filename") or "clean")).stem
        return _file_response(job_id, "clean_path", f"{name}.clean.csv", "text/csv")

    @app.get("/api/jobs/{job_id}/qa")
    def download_qa(job_id: str) -> FileResponse:
        name = Path(str(_get_job(job_id).get("filename") or "qa")).stem
        return _file_response(job_id, "qa_json_path", f"{name}.qa.json", "application/json")

    return app


app = create_app()
