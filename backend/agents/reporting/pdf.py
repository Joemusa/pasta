"""Draw a Smollan-styled PDF from QA + commercial snapshot. Deterministic — no LLM."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pymupdf

from backend.agents.data_qa.models import QAReport
from backend.agents.reporting.insights import CommercialSnapshot, RankedShare

W, H = 960.0, 540.0
NAVY = (0x12 / 255, 0x2A / 255, 0x4A / 255)
BLUE = (0x1F / 255, 0x5F / 255, 0xA8 / 255)
ORANGE = (0xD0 / 255, 0x5A / 255, 0x1A / 255)
RED = (0xB0 / 255, 0x28 / 255, 0x28 / 255)
GREEN = (0x1B / 255, 0x7A / 255, 0x3A / 255)
INK = (0x11 / 255, 0x11 / 255, 0x11 / 255)
MUTED = (0x3D / 255, 0x4A / 255, 0x55 / 255)
WHITE = (1, 1, 1)
LIGHT = (0xF3 / 255, 0xF5 / 255, 0xF7 / 255)
LINE = (0xC8 / 255, 0xD0 / 255, 0xD8 / 255)
LIME = (0x88 / 255, 0xC0 / 255, 0x40 / 255)
CYAN = (0, 0xB8 / 255, 0xF0 / 255)

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = REPO_ROOT / "templates" / "Smollan_Unilever_Template.pdf"
LOGO = REPO_ROOT / "templates" / "smollan_logo_content.png"

STATUS_COLOR = {
    "PASS": GREEN,
    "PASS_WITH_WARNINGS": ORANGE,
    "PARTIAL_PASS": ORANGE,
    "FAIL": RED,
}


def _fmt_value(value: float) -> str:
    abs_v = abs(value)
    if abs_v >= 1_000_000_000:
        return f"R{value / 1_000_000_000:.1f}bn"
    if abs_v >= 1_000_000:
        return f"R{value / 1_000_000:.1f}m"
    if abs_v >= 1_000:
        return f"R{value / 1_000:.0f}k"
    return f"R{value:,.0f}"


def _text(page: pymupdf.Page, rect: pymupdf.Rect, text: str, *, size: float, color=INK, font="helv", align=0) -> None:
    page.insert_textbox(rect, text, fontsize=size, fontname=font, color=color, align=align)


def _bar_chart(items: list[RankedShare], path: Path, xlabel: str) -> Path | None:
    if not items:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    labels = [item.name[:28] for item in reversed(items)]
    values = [item.share * 100 for item in reversed(items)]
    fig, ax = plt.subplots(figsize=(7.2, 3.8), dpi=160)
    ax.barh(labels, values, color="#1F5FA8", height=0.62)
    ax.set_xlabel(xlabel, color="#111111")
    ax.tick_params(colors="#111111")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#C8D0D8")
    ax.spines["bottom"].set_color("#C8D0D8")
    ax.grid(axis="x", color="#EEF2F6")
    xmax = max(values) * 1.22 if values else 1
    ax.set_xlim(0, xmax)
    for bar, item in zip(ax.patches, reversed(items), strict=False):
        ax.text(
            item.share * 100 + xmax * 0.02,
            bar.get_y() + bar.get_height() / 2,
            f"{item.share * 100:.0f}%",
            va="center",
            fontsize=10,
            color="#111111",
            fontweight="bold",
        )
    fig.tight_layout(pad=0.4)
    fig.savefig(path, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    return path


def _shell(page: pymupdf.Page, title: str, page_no: int, total: int) -> None:
    page.draw_rect(pymupdf.Rect(0, 0, W, H), color=WHITE, fill=WHITE)
    page.draw_rect(pymupdf.Rect(0, 0, 10, H), color=NAVY, fill=NAVY)
    page.draw_rect(pymupdf.Rect(0, 0, W, 6), color=NAVY, fill=NAVY)
    _text(page, pymupdf.Rect(28, 16, 720, 52), title, size=22, color=NAVY, font="hebo")
    page.draw_rect(pymupdf.Rect(28, 52, 180, 57), color=ORANGE, fill=ORANGE)
    if LOGO.exists():
        page.insert_image(pymupdf.Rect(780, 12, 940, 46), filename=str(LOGO), keep_proportion=True)
    page.draw_rect(pymupdf.Rect(0, 512, W, H), color=LIGHT, fill=LIGHT)
    _text(
        page,
        pymupdf.Rect(28, 516, 720, 536),
        "FMCG Commercial Intelligence  ·  Data QA Agent  ·  Report Agent  ·  source file is never overwritten",
        size=9,
        color=MUTED,
    )
    _text(page, pymupdf.Rect(820, 516, 940, 536), f"{page_no} / {total}", size=10, color=NAVY, font="hebo", align=2)


def _kpi(
    page: pymupdf.Page,
    x: float,
    y: float,
    w: float,
    h: float,
    label: str,
    value: str,
    note: str,
    accent=BLUE,
) -> None:
    page.draw_rect(pymupdf.Rect(x, y, x + w, y + h), color=LINE, fill=LIGHT, width=0.6)
    page.draw_rect(pymupdf.Rect(x, y, x + 7, y + h), color=accent, fill=accent)
    _text(page, pymupdf.Rect(x + 16, y + 8, x + w - 10, y + 26), label.upper(), size=9, color=MUTED, font="hebo")
    value_size = 14 if len(value) > 16 else 20
    page.insert_text(
        pymupdf.Point(x + 16, y + 48),
        value,
        fontsize=value_size,
        fontname="hebo",
        color=NAVY,
    )
    _text(page, pymupdf.Rect(x + 16, y + 70, x + w - 10, y + h - 6), note, size=10, color=INK)


def write_pdf(
    report: QAReport,
    snapshot: CommercialSnapshot,
    output_path: Path,
    *,
    source_name: str,
    chart_dir: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open()
    status = report.status.value
    accent = STATUS_COLOR.get(status, ORANGE)
    total_pages = 5 if snapshot.has_data else 4

    # 1. Cover
    cover = doc.new_page(width=W, height=H)
    if TEMPLATE.exists():
        src = pymupdf.open(TEMPLATE)
        cover.show_pdf_page(cover.rect, src, 0)
        src.close()
    else:
        cover.draw_rect(cover.rect, color=NAVY, fill=NAVY)
    cover.draw_rect(pymupdf.Rect(36, 248, 580, 410), color=NAVY, fill=NAVY)
    _text(cover, pymupdf.Rect(48, 258, 560, 298), "Commercial Intelligence", size=24, color=WHITE, font="hebo")
    _text(cover, pymupdf.Rect(48, 300, 560, 330), "Data QA + category report", size=16, color=WHITE, font="hebo")
    _text(cover, pymupdf.Rect(48, 332, 560, 356), source_name[:80], size=12, color=CYAN)
    _text(
        cover,
        pymupdf.Rect(48, 364, 560, 396),
        f"{status.replace('_', ' ')}  ·  quality {report.quality_score}",
        size=14,
        color=LIME,
        font="hebo",
    )
    _text(cover, pymupdf.Rect(48, 500, 500, 524), "A SMOLLAN COMPANY", size=10, color=WHITE)

    # 2. QA summary
    page = doc.new_page(width=W, height=H)
    _shell(page, "Data QA Agent", 2, total_pages)
    _kpi(page, 28, 72, 220, 100, "Status", status.replace("_", " "), "Deterministic Python - no LLM", accent)
    _kpi(page, 256, 72, 220, 100, "Quality score", str(report.quality_score), "0-100 after populated-row scoring", BLUE)
    _kpi(
        page,
        484,
        72,
        220,
        100,
        "Rows",
        f"{report.row_count_clean:,}",
        f"{report.row_count_raw:,} in  ·  {report.rows_dropped:,} excluded",
        BLUE,
    )
    _kpi(
        page,
        712,
        72,
        220,
        100,
        "History",
        f"{report.distinct_dates} dates",
        f"{report.date_min or '-'} to {report.date_max or '-'}",
        BLUE,
    )
    _text(page, pymupdf.Rect(28, 188, 480, 212), "Column mapping", size=14, color=NAVY, font="hebo")
    mapping_lines = [f"{src}  ->  {dst}" for src, dst in list(report.column_mapping.items())[:12]]
    _text(page, pymupdf.Rect(28, 214, 470, 430), "\n".join(mapping_lines) or "No columns mapped", size=11, color=INK)
    _text(page, pymupdf.Rect(500, 188, 920, 212), "Downstream capabilities", size=14, color=NAVY, font="hebo")
    y = 220
    for name, enabled in report.capabilities.model_dump().items():
        color = GREEN if enabled else MUTED
        mark = "READY" if enabled else "BLOCKED"
        page.draw_rect(pymupdf.Rect(500, y, 932, y + 36), color=LINE, fill=LIGHT, width=0.5)
        _text(page, pymupdf.Rect(512, y + 8, 760, y + 30), name.replace("_", " "), size=12, color=NAVY, font="hebo")
        _text(page, pymupdf.Rect(770, y + 8, 920, y + 30), mark, size=12, color=color, font="hebo", align=2)
        y += 42

    # 3. Issues
    page = doc.new_page(width=W, height=H)
    _shell(page, "What the Data QA Agent found", 3, total_pages)
    issues = (
        [("CRITICAL", issue, RED) for issue in report.critical_issues]
        + [("WARNING", issue, ORANGE) for issue in report.warnings]
        + [("INFO", issue, BLUE) for issue in report.info]
    )
    if not issues:
        _text(
            page,
            pymupdf.Rect(28, 90, 900, 140),
            "No issues. File passed with a clean QA report.",
            size=16,
            color=GREEN,
            font="hebo",
        )
    y = 78
    for severity, issue, color in issues[:9]:
        page.draw_rect(pymupdf.Rect(28, y, 932, y + 42), color=LINE, fill=WHITE, width=0.5)
        page.draw_rect(pymupdf.Rect(28, y, 36, y + 42), color=color, fill=color)
        _text(page, pymupdf.Rect(48, y + 6, 200, y + 22), severity, size=9, color=color, font="hebo")
        _text(page, pymupdf.Rect(200, y + 6, 900, y + 22), issue.code, size=11, color=NAVY, font="hebo")
        _text(page, pymupdf.Rect(48, y + 22, 900, y + 40), issue.message[:140], size=10, color=INK)
        y += 46
    if len(issues) > 9:
        extra = f"+ {len(issues) - 9} more in the JSON report"
        _text(page, pymupdf.Rect(28, y, 900, y + 24), extra, size=11, color=MUTED)

    # 4. Commercial snapshot (clean table)
    page_no = 4
    if snapshot.has_data:
        page = doc.new_page(width=W, height=H)
        _shell(page, "Clean table - commercial snapshot", 4, total_pages)
        _kpi(
            page,
            28,
            72,
            226,
            100,
            "Sales value",
            _fmt_value(snapshot.total_value),
            f"{snapshot.row_count:,} clean rows",
            BLUE,
        )
        _kpi(page, 262, 72, 226, 100, "Volume", f"{snapshot.total_volume:,.0f}", "sum of sales_volume", BLUE)
        _kpi(
            page,
            496,
            72,
            226,
            100,
            "Products",
            f"{snapshot.n_products:,}",
            f"{snapshot.n_manufacturers} manufacturers",
            BLUE,
        )
        _kpi(
            page,
            730,
            72,
            202,
            100,
            "Retailers",
            f"{snapshot.n_retailers:,}",
            f"{snapshot.n_regions} regions  ·  {snapshot.n_dates} dates",
            BLUE,
        )
        chart = _bar_chart(
            snapshot.top_manufacturers or snapshot.top_products,
            chart_dir / "top_share.png",
            "Share of clean sales value (%)",
        )
        _text(page, pymupdf.Rect(28, 184, 520, 208), "Share of value", size=14, color=NAVY, font="hebo")
        if chart and chart.exists():
            page.insert_image(pymupdf.Rect(20, 208, 520, 500), filename=str(chart), keep_proportion=True)
        _text(page, pymupdf.Rect(540, 184, 932, 208), "Top products", size=14, color=NAVY, font="hebo")
        y = 216
        ranking = snapshot.top_products or snapshot.top_manufacturers
        for item in ranking[:8]:
            page.draw_rect(pymupdf.Rect(540, y, 932, y + 32), color=LINE, fill=LIGHT, width=0.4)
            _text(page, pymupdf.Rect(552, y + 8, 780, y + 26), item.name[:32], size=10, color=INK)
            _text(
                page,
                pymupdf.Rect(784, y + 8, 920, y + 26),
                f"{item.share * 100:.1f}%",
                size=10,
                color=NAVY,
                font="hebo",
                align=2,
            )
            y += 34
        page_no = 5

    # Last. Next steps
    page = doc.new_page(width=W, height=H)
    if TEMPLATE.exists():
        src = pymupdf.open(TEMPLATE)
        last_idx = src.page_count - 1
        page.show_pdf_page(page.rect, src, last_idx)
        src.close()
        _text(page, pymupdf.Rect(520, 200, 900, 250), "Thank You!", size=32, color=WHITE, font="hebo")
        _text(
            page,
            pymupdf.Rect(520, 260, 900, 330),
            "Data QA complete. Download the PDF, clean CSV, and JSON from the workspace.",
            size=12,
            color=WHITE,
        )
    else:
        _shell(page, "Next", page_no, total_pages)
        ready = "ready" if report.analysis_ready else "not ready"
        _text(
            page,
            pymupdf.Rect(28, 90, 900, 160),
            f"This file is {ready} for commercial analysis.",
            size=18,
            color=NAVY,
            font="hebo",
        )
        _text(
            page,
            pymupdf.Rect(28, 170, 900, 280),
            "Distribution, Price, and Promotion agents consume this QA output. They are not run from this screen yet.",
            size=14,
            color=INK,
        )

    doc.save(output_path)
    doc.close()
    return output_path
