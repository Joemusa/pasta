"""Upload pipeline: Data QA Agent then Report Agent."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path

import pandas as pd

from backend.agents.data_qa import run_data_qa
from backend.agents.data_qa.models import QAReport
from backend.agents.reporting import build_snapshot, run_report_agent
from backend.agents.reporting.insights import CommercialSnapshot

logger = logging.getLogger("backend.pipeline")

StageCallback = Callable[[str], None]


class PipelineResult:
    def __init__(
        self,
        report: QAReport,
        snapshot: CommercialSnapshot,
        pdf_path: Path,
        clean_path: Path | None,
        qa_json_path: Path | None,
        exclusions_path: Path | None,
    ) -> None:
        self.report = report
        self.snapshot = snapshot
        self.pdf_path = pdf_path
        self.clean_path = clean_path
        self.qa_json_path = qa_json_path
        self.exclusions_path = exclusions_path

    def summary(self) -> dict:
        return {
            "status": self.report.status.value,
            "analysis_ready": self.report.analysis_ready,
            "quality_score": self.report.quality_score,
            "critical_issues": [issue.model_dump(mode="json") for issue in self.report.critical_issues],
            "warnings": [issue.model_dump(mode="json") for issue in self.report.warnings],
            "info": [issue.model_dump(mode="json") for issue in self.report.info],
            "capabilities": self.report.capabilities.model_dump(mode="json"),
            "column_mapping": self.report.column_mapping,
            "unmapped_columns": self.report.unmapped_columns,
            "missing_canonical_fields": self.report.missing_canonical_fields,
            "row_count_raw": self.report.row_count_raw,
            "row_count_clean": self.report.row_count_clean,
            "rows_dropped": self.report.rows_dropped,
            "rows_empty_metrics": self.report.rows_empty_metrics,
            "distinct_dates": self.report.distinct_dates,
            "date_min": self.report.date_min,
            "date_max": self.report.date_max,
            "source_name": Path(self.report.input_file).name,
            "snapshot": self.snapshot.to_json_dict(),
            "has_pdf": self.pdf_path.exists(),
            "has_clean": bool(self.clean_path and self.clean_path.exists()),
            "has_exclusions": bool(self.exclusions_path and self.exclusions_path.exists()),
        }


def _optional_path(value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.exists() else None


def run_pipeline(source: Path, job_dir: Path, on_stage: StageCallback | None = None) -> PipelineResult:
    """Run Data QA then write a PDF report into job_dir."""
    job_dir.mkdir(parents=True, exist_ok=True)
    if on_stage:
        on_stage("qa")
    logger.info("pipeline_qa source=%s job_dir=%s", source, job_dir)
    report = run_data_qa(source, data_root=job_dir, write_outputs=True)

    clean_path = _optional_path(report.clean_output_path)
    if clean_path is not None:
        clean = pd.read_csv(clean_path)
    else:
        clean = pd.DataFrame()
    snapshot = build_snapshot(clean)

    if on_stage:
        on_stage("report")
    pdf_path = job_dir / "report.pdf"
    run_report_agent(
        report,
        snapshot,
        pdf_path,
        source_name=source.name,
        chart_dir=job_dir / "charts",
    )
    qa_json = _optional_path(report.report_output_path)
    exclusions = _optional_path(report.exclusions_output_path)
    result = PipelineResult(
        report=report,
        snapshot=snapshot,
        pdf_path=pdf_path,
        clean_path=clean_path,
        qa_json_path=qa_json,
        exclusions_path=exclusions,
    )
    (job_dir / "summary.json").write_text(json.dumps(result.summary(), indent=2) + "\n", encoding="utf-8")
    logger.info("pipeline_done status=%s pdf=%s", report.status.value, pdf_path)
    return result
