from __future__ import annotations

from pathlib import Path

import pymupdf

from backend.pipeline import run_pipeline


def test_pipeline_writes_pdf_for_sample(tmp_path: Path) -> None:
    source = Path("backend/data/raw/sample_pos.csv")
    result = run_pipeline(source, tmp_path / "job")
    assert result.pdf_path.exists()
    assert result.pdf_path.read_bytes()[:4] == b"%PDF"
    doc = pymupdf.open(result.pdf_path)
    assert doc.page_count >= 4
    assert result.report.analysis_ready is True
    assert result.snapshot.has_data is True
    summary = result.summary()
    assert summary["has_pdf"] is True
    assert summary["capabilities"]["commercial_brain"] is True
