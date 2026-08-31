"""Render executive and full PDFs from the Opportunity Pulse JSON. Values are not recalculated."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

INK = colors.HexColor("#12202b")
MUTED = colors.HexColor("#5c6e7a")
LINE = colors.HexColor("#d7dfe6")
PAPER = colors.HexColor("#f7f4ee")
TEAL = colors.HexColor("#0f6e62")
GOLD = colors.HexColor("#b8862a")
HIGH = colors.HexColor("#2a7a4e")
WHITE = colors.white

FONT_DIR = Path("/usr/share/fonts/truetype/liberation")
_FONTS_READY = False


def _fonts() -> None:
    global _FONTS_READY
    if _FONTS_READY:
        return
    mapping = {
        "LibSans": "LiberationSans-Regular.ttf",
        "LibSans-Bold": "LiberationSans-Bold.ttf",
        "LibSans-Italic": "LiberationSans-Italic.ttf",
        "LibSerif": "LiberationSerif-Regular.ttf",
        "LibSerif-Bold": "LiberationSerif-Bold.ttf",
    }
    for name, filename in mapping.items():
        path = FONT_DIR / filename
        if path.is_file():
            pdfmetrics.registerFont(TTFont(name, str(path)))
    _FONTS_READY = True


def money(value: Any) -> str:
    if value is None:
        return "Not available"
    return f"R{float(value):,.0f}"


def number(value: Any, digits: int = 1) -> str:
    if value is None:
        return "Not available"
    return f"{float(value):,.{digits}f}"


def metric_text(metric: dict[str, Any] | None, *, kind: str = "num") -> str:
    if not metric or not metric.get("available") or metric.get("value") is None:
        return "Not available"
    if kind == "money":
        return money(metric["value"])
    if kind == "int":
        return f"{float(metric['value']):,.0f}"
    return number(metric["value"])


def _styles() -> dict[str, ParagraphStyle]:
    _fonts()
    base = getSampleStyleSheet()
    sans = "LibSans" if "LibSans" in pdfmetrics.getRegisteredFontNames() else "Helvetica"
    sans_bold = "LibSans-Bold" if "LibSans-Bold" in pdfmetrics.getRegisteredFontNames() else "Helvetica-Bold"
    serif_bold = "LibSerif-Bold" if "LibSerif-Bold" in pdfmetrics.getRegisteredFontNames() else "Times-Bold"
    return {
            "kicker": ParagraphStyle(
                "kicker", parent=base["Normal"], fontName=sans_bold, fontSize=8, textColor=TEAL, spaceAfter=2
            ),
        "title": ParagraphStyle(
            "title", parent=base["Normal"], fontName=serif_bold, fontSize=18, textColor=INK, leading=22, spaceAfter=0
        ),
        "document": ParagraphStyle(
            "document", parent=base["Normal"], fontName=sans_bold, fontSize=11, textColor=INK, spaceAfter=2
        ),
        "tagline": ParagraphStyle(
            "tagline", parent=base["Normal"], fontName=sans, fontSize=9, textColor=MUTED, spaceAfter=8
        ),
        "headline": ParagraphStyle(
            "headline", parent=base["Normal"], fontName=serif_bold, fontSize=14, textColor=INK, leading=18, spaceAfter=6
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"], fontName=sans, fontSize=8.5, textColor=INK, leading=11.5, spaceAfter=4
        ),
        "muted": ParagraphStyle(
            "muted", parent=base["Normal"], fontName=sans, fontSize=8, textColor=MUTED, leading=11, spaceAfter=4
        ),
        "section": ParagraphStyle(
            "section",
            parent=base["Normal"],
            fontName=sans_bold,
            fontSize=9,
            textColor=TEAL,
            spaceBefore=8,
            spaceAfter=4,
        ),
        "small": ParagraphStyle(
            "small", parent=base["Normal"], fontName=sans, fontSize=7.5, textColor=MUTED, leading=10
        ),
        "kpi_label": ParagraphStyle(
            "kpi_label", parent=base["Normal"], fontName=sans, fontSize=7, textColor=MUTED, alignment=TA_CENTER
        ),
        "kpi_value": ParagraphStyle(
            "kpi_value",
            parent=base["Normal"],
            fontName=sans_bold,
            fontSize=11,
            textColor=INK,
            alignment=TA_CENTER,
            leading=14,
        ),
        "table": ParagraphStyle(
            "table", parent=base["Normal"], fontName=sans, fontSize=7.5, textColor=INK, leading=10
        ),
        "table_head": ParagraphStyle(
            "table_head", parent=base["Normal"], fontName=sans_bold, fontSize=7, textColor=WHITE, leading=9
        ),
        "opp_title": ParagraphStyle(
            "opp_title",
            parent=base["Normal"],
            fontName=serif_bold,
            fontSize=13,
            textColor=INK,
            leading=17,
            spaceAfter=6,
        ),
        "right": ParagraphStyle(
            "right", parent=base["Normal"], fontName=sans, fontSize=8, textColor=MUTED, alignment=TA_RIGHT
        ),
        "center": ParagraphStyle(
            "center", parent=base["Normal"], fontName=sans, fontSize=8, textColor=MUTED, alignment=TA_CENTER
        ),
    }


def _header_footer(canvas, doc, report: dict[str, Any], *, page_label: str) -> None:
    canvas.saveState()
    canvas.setFillColor(INK)
    canvas.rect(0, A4[1] - 14 * mm, A4[0], 14 * mm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawString(16 * mm, A4[1] - 8.5 * mm, "UNILEVER SOUTH AFRICA  ·  COMMERCIAL OPPORTUNITY PULSE")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(A4[0] - 16 * mm, A4[1] - 8.5 * mm, f"POS {report.get('current_period') or ''}")
    canvas.setFillColor(TEAL)
    canvas.rect(0, 0, A4[0], 10 * mm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(16 * mm, 4 * mm, "Addressable opportunity estimate · not guaranteed incremental sales")
    canvas.drawRightString(A4[0] - 16 * mm, 4 * mm, f"{page_label}  {doc.page}")
    canvas.restoreState()


def _kpi_strip(styles: dict[str, ParagraphStyle], cells: list[tuple[str, str]]) -> Table:
    data = [
        [Paragraph(label.upper(), styles["kpi_label"]) for label, _ in cells],
        [Paragraph(value, styles["kpi_value"]) for _, value in cells],
    ]
    table = Table(data, colWidths=[(A4[0] - 32 * mm) / len(cells)] * len(cells))
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fffdf8")),
                ("BOX", (0, 0), (-1, -1), 0.4, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return table


def _simple_bars(values: list[tuple[str, float]], *, caption: str, styles: dict[str, ParagraphStyle]) -> list[Any]:
    if not values:
        return []
    peak = max(item[1] for item in values) or 1
    width = A4[0] - 32 * mm
    rows: list[list[Any]] = []
    for label, value in values:
        bar_w = max(2, (value / peak) * (width * 0.55))
        bar = Table([[""]], colWidths=[bar_w], rowHeights=[8])
        bar.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), TEAL), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        rows.append(
            [
                Paragraph(label, styles["table"]),
                bar,
                Paragraph(money(value), styles["table"]),
            ]
        )
    table = Table(rows, colWidths=[width * 0.32, width * 0.55, width * 0.13])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return [table, Paragraph(caption, styles["small"]), Spacer(1, 4)]


def _coverage_bars(rows: list[dict[str, Any]], styles: dict[str, ParagraphStyle]) -> list[Any]:
    if not rows:
        return []
    peak = max(max(item["current_stores"], item["benchmark_stores"]) for item in rows) or 1
    width = A4[0] - 32 * mm
    flow: list[Any] = []
    for item in rows:
        current_w = max(2, (item["current_stores"] / peak) * (width * 0.5))
        bench_w = max(2, (item["benchmark_stores"] / peak) * (width * 0.5))
        current = Table([[""]], colWidths=[current_w], rowHeights=[6])
        current.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), TEAL)]))
        bench = Table([[""]], colWidths=[bench_w], rowHeights=[6])
        bench.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), GOLD)]))
        flow.append(
            Paragraph(
                f"#{item['rank']} listed {item['current_stores']:.0f} vs benchmark {item['benchmark_stores']:.0f}",
                styles["table"],
            )
        )
        flow.append(Table([[current], [bench]], colWidths=[width * 0.7]))
    return flow


def _box(title: str, body: str, styles: dict[str, ParagraphStyle], *, note: str | None = None) -> Table:
    content = [
        [Paragraph(title.upper(), styles["section"])],
        [Paragraph(body, styles["body"])],
    ]
    if note:
        content.append([Paragraph(note, styles["small"])])
    table = Table(content, colWidths=[A4[0] - 32 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eef4f2")),
                ("BOX", (0, 0), (-1, -1), 0.4, TEAL),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (0, 0), 2),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 6),
            ]
        )
    )
    return table


def _top_table(report: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    header = ["Rank", "Product", "Retailer", "Region", "Lever", "Opportunity", "Confidence"]
    data = [[Paragraph(item, styles["table_head"]) for item in header]]
    for row in report["opportunities"]:
        data.append(
            [
                Paragraph(str(row["rank"]), styles["table"]),
                Paragraph(str(row["product"]), styles["table"]),
                Paragraph(str(row["retailer"]), styles["table"]),
                Paragraph(str(row["region"]), styles["table"]),
                Paragraph(str(row["lever"]), styles["table"]),
                Paragraph(money(row["addressable_value"]), styles["table"]),
                Paragraph(str(row["confidence"]), styles["table"]),
            ]
        )
    widths = [22 * mm, 48 * mm, 28 * mm, 24 * mm, 28 * mm, 28 * mm, 22 * mm]
    table = Table(data, colWidths=widths)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), INK),
                ("BACKGROUND", (0, 1), (-1, -1), WHITE),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("GRID", (0, 0), (-1, -1), 0.3, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def executive_story(report: dict[str, Any]) -> list[Any]:
    styles = _styles()
    story = report["story"]
    total = report["top3_sum"]
    quality = report["quality"]
    flow: list[Any] = [
        Paragraph("UNILEVER SOUTH AFRICA", styles["kicker"]),
        Paragraph("COMMERCIAL OPPORTUNITY PULSE", styles["title"]),
        Paragraph(report["tagline"], styles["tagline"]),
        Paragraph(
            f"POS period {quality.get('current_period') or 'Not available'} · "
            f"{quality.get('pos_weeks') or 'Not available'} POS weeks · "
            f"Ranking: Commercial Brain V1",
            styles["muted"],
        ),
        Paragraph(story.get("headline") or "", styles["headline"]),
        Paragraph(story.get("supporting_line") or "", styles["body"]),
        Paragraph(f"<b>Commercial implication.</b> {story.get('commercial_implication') or ''}", styles["body"]),
        Spacer(1, 4),
        _kpi_strip(
            styles,
            [
                ("Addressable opportunity estimate", money(total["addressable_value"])),
                ("Addressable volume", f"{total['addressable_volume']:,.0f} units"),
                ("Dominant lever", str(story.get("dominant_lever") or "Not available")),
            ],
        ),
        Paragraph(total["disclaimer"], styles["small"]),
        Paragraph("TOP 3 OPPORTUNITIES", styles["section"]),
        _top_table(report, styles),
        Spacer(1, 6),
        Paragraph("Addressable value by Brain rank", styles["section"]),
    ]
    flow.extend(
        _simple_bars(
            [
                (f"#{item['rank']} {item['product']}", float(item["addressable_value"]))
                for item in report["opportunities"]
            ],
            caption=report["charts"]["ranking_caption"],
            styles=styles,
        )
    )
    macro = report.get("macro") or {}
    if macro.get("included"):
        flow.append(
            _box(
                "Supporting macro context",
                f"{macro.get('signal') or ''} · {macro.get('evidence') or ''}",
                styles,
                note=macro.get("disclaimer"),
            )
        )
    else:
        flow.append(Paragraph("Supporting macro context: Not available", styles["muted"]))
    flow.append(Spacer(1, 6))
    social = report.get("social") or {}
    if social.get("connected"):
        lines = " ".join(item.get("text") or "" for item in social.get("validated_observations") or [])
        period = ""
        if social.get("observation_start") and social.get("observation_end"):
            period = f" Observation window {social['observation_start']} to {social['observation_end']}."
        flow.append(
            _box(
                "Social intelligence",
                f"{social.get('display')}. {lines}{period}",
                styles,
                note=social.get("disclaimer"),
            )
        )
    else:
        flow.append(Paragraph("Social intelligence: not connected", styles["body"]))
        flow.append(Paragraph(social.get("disclaimer") or "", styles["small"]))
    flow.append(
        Paragraph(
            f"Source: Commercial Brain V1 ({report.get('sources', {}).get('brain') or 'frozen JSON'}). "
            f"Narrative: Storytelling Engine V1. Causality claim: none.",
            styles["small"],
        )
    )
    return flow


def opportunity_pages(report: dict[str, Any]) -> list[Any]:
    styles = _styles()
    flow: list[Any] = []
    for item in report["opportunities"]:
        flow.append(PageBreak())
        prov = item.get("provenance") or {}
        block = [
            Paragraph(f"OPPORTUNITY {item['rank']}  ·  {item['lever']}  ·  {item['confidence']}", styles["kicker"]),
            Paragraph(item.get("headline") or "", styles["opp_title"]),
            Paragraph(
                f"{item.get('product')}  ·  {item.get('brand') or 'Not available'}  ·  "
                f"{item.get('retailer')}  ·  {item.get('region')}",
                styles["muted"],
            ),
            _kpi_strip(
                styles,
                [
                    ("Current sales", metric_text(item.get("current_sales"), kind="money")),
                    ("Addressable value", money(item.get("addressable_value"))),
                    ("Addressable volume", number(item.get("addressable_volume"))),
                    ("Confidence", str(item.get("confidence") or "Not available")),
                ],
            ),
            Spacer(1, 6),
            Paragraph("Commercial evidence", styles["section"]),
            Paragraph(
                f"Store gap: {metric_text(item.get('store_gap'), kind='int')} · "
                f"Current stores: {metric_text(item.get('current_stores'), kind='int')} · "
                f"Benchmark stores: {metric_text(item.get('benchmark_stores'), kind='int')} · "
                f"Value/store: {metric_text(item.get('value_per_store'), kind='money')} · "
                f"Volume/store: {metric_text(item.get('volume_per_store'))}",
                styles["body"],
            ),
        ]
        coverage_rows = [
            row for row in report["charts"].get("coverage") or [] if row["rank"] == item["rank"]
        ]
        if coverage_rows:
            block.append(Paragraph("Store coverage vs benchmark", styles["section"]))
            block.extend(_coverage_bars(coverage_rows, styles))
            block.append(Paragraph(report["charts"]["coverage_caption"], styles["small"]))
        sales_rows = [
            row for row in report["charts"].get("sales_versus_opportunity") or [] if row["rank"] == item["rank"]
        ]
        if sales_rows:
            row = sales_rows[0]
            block.append(Paragraph("Current sales vs addressable opportunity", styles["section"]))
            block.extend(
                _simple_bars(
                    [
                        ("Current sales", float(row["current_sales"])),
                        ("Addressable opportunity", float(row["addressable_value"])),
                    ],
                    caption=report["charts"]["sales_caption"],
                    styles=styles,
                )
            )
        block.extend(
            [
                Paragraph("Why this matters", styles["section"]),
                Paragraph(item.get("why") or "Not available", styles["body"]),
                Paragraph("Recommended action", styles["section"]),
                Paragraph(item.get("recommended_action") or "Not available", styles["body"]),
                Paragraph("Supporting evidence", styles["section"]),
            ]
        )
        evidence = item.get("evidence") or []
        if evidence:
            for line in evidence:
                block.append(Paragraph(f"• {line}", styles["body"]))
        else:
            block.append(Paragraph("Not available", styles["muted"]))
        risks = item.get("limitations") or []
        block.append(Paragraph("Risks / limitations", styles["section"]))
        block.append(
            Paragraph(
                f"Double-counting risk: {item.get('double_counting_risk') or 'Not available'}. "
                "Addressable value is not guaranteed incremental sales.",
                styles["body"],
            )
        )
        for line in risks[:6]:
            block.append(Paragraph(f"• {line}", styles["small"]))
        block.append(Paragraph("Source / provenance", styles["section"]))
        block.append(
            Paragraph(
                f"Agent: {prov.get('agent') or 'Commercial Brain V1'}. "
                f"Specialist: {prov.get('specialist_agent') or 'Not available'}. "
                f"Source: {prov.get('source') or 'Not available'}. "
                f"Observation date: {prov.get('observation_date') or 'Not available'}.",
                styles["small"],
            )
        )
        flow.append(KeepTogether(block))
    return flow


def methodology_page(report: dict[str, Any]) -> list[Any]:
    styles = _styles()
    quality = report.get("quality") or {}
    flow = [
        PageBreak(),
        Paragraph("METHODOLOGY AND LIMITATIONS", styles["kicker"]),
        Paragraph("How to read this pulse", styles["opp_title"]),
        Paragraph(report.get("methodology") or "", styles["body"]),
        Paragraph("Coverage", styles["section"]),
        Paragraph(
            f"POS period: {quality.get('current_period') or 'Not available'}. "
            f"POS weeks: {quality.get('pos_weeks') if quality.get('pos_weeks') is not None else 'Not available'}.",
            styles["body"],
        ),
        Paragraph(
            "Price/promotion weeks: "
            + str(
                quality.get("price_promotion_weeks")
                if quality.get("price_promotion_weeks") is not None
                else "Not available"
            )
            + f". SKU identity: {quality.get('sku_identity')}.",
            styles["body"],
        ),
        Paragraph("Limitations", styles["section"]),
    ]
    for note in (report.get("limitations") or [])[:18]:
        flow.append(Paragraph(f"• {note}", styles["small"]))
    sources = report.get("sources") or {}
    flow.append(Paragraph("Provenance", styles["section"]))
    for key, value in sources.items():
        flow.append(Paragraph(f"• {key}: {value or 'Not available'}", styles["small"]))
    flow.append(
        Paragraph(
            "The JSON report is the source of truth. This PDF copies those values and does not recalculate "
            "Commercial Brain ranking, specialist scores, or confidence.",
            styles["body"],
        )
    )
    return flow


def _build(path: Path, report: dict[str, Any], flow: list[Any], *, page_label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=20 * mm,
        bottomMargin=14 * mm,
        title="Unilever South Africa Commercial Opportunity Pulse",
        author="Commercial Intelligence V1",
    )
    doc.build(
        flow,
        onFirstPage=lambda canvas, document: _header_footer(canvas, document, report, page_label=page_label),
        onLaterPages=lambda canvas, document: _header_footer(canvas, document, report, page_label=page_label),
    )


def render_executive_pdf(report: dict[str, Any], path: str | Path) -> Path:
    output = Path(path)
    _build(output, report, executive_story(report), page_label="Executive")
    return output


def render_full_pdf(report: dict[str, Any], path: str | Path) -> Path:
    output = Path(path)
    flow = executive_story(report) + opportunity_pages(report) + methodology_page(report)
    _build(output, report, flow, page_label="Full briefing")
    return output
