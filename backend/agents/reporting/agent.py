"""Report Agent: turn QA output + clean table into a PDF presentation."""

from __future__ import annotations

from pathlib import Path

from backend.agents.data_qa.models import QAReport
from backend.agents.reporting.insights import CommercialSnapshot
from backend.agents.reporting.pdf import write_pdf


def run_report_agent(
    report: QAReport,
    snapshot: CommercialSnapshot,
    output_path: str | Path,
    *,
    source_name: str,
    chart_dir: str | Path | None = None,
) -> Path:
    pdf_path = Path(output_path)
    charts = Path(chart_dir) if chart_dir else pdf_path.parent / "charts"
    return write_pdf(report, snapshot, pdf_path, source_name=source_name, chart_dir=charts)
