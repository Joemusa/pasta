#!/usr/bin/env python3
"""Build a 3-slide Pasta / Noodles review from the Unilever monthly export."""

from __future__ import annotations

import re
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "02. Monthly Time Groupings Export_2026-08-18 (1).xlsx"
OUTPUT_DIR = ROOT / "output"
CHART_DIR = OUTPUT_DIR / "charts"
DECK = OUTPUT_DIR / "Unilever_Pasta_Noodles_Jun2026.pptx"

NAVY = RGBColor(0x0B, 0x25, 0x45)
BLUE = RGBColor(0x1B, 0x4F, 0x8A)
TEAL = RGBColor(0x0E, 0x7C, 0x7B)
ORANGE = RGBColor(0xC4, 0x5C, 0x26)
RED = RGBColor(0x9B, 0x2C, 0x2C)
INK = RGBColor(0x1A, 0x1A, 0x1A)
MUTED = RGBColor(0x5C, 0x6B, 0x73)
LIGHT = RGBColor(0xF4, 0xF6, 0xF8)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LINE = RGBColor(0xD5, 0xDB, 0xE0)

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)


def load_data() -> pd.DataFrame:
    df = pd.read_excel(SOURCE, skiprows=3)
    df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed")]
    df = df[df["Full Date"] != "Grand Totals"].copy()
    df.columns = [
        "month",
        "category",
        "sku",
        "brand",
        "manufacturer",
        "avg_price",
        "value",
        "volume",
    ]
    return df


def pack_grams(name: str) -> float | None:
    match = re.search(r"(\d+)\s*g", str(name), re.I)
    return float(match.group(1)) if match else None


def pasta_table(df: pd.DataFrame) -> pd.DataFrame:
    pasta = df[df["category"] == "Pasta"].copy()
    pasta["pack_g"] = pasta["sku"].map(pack_grams)
    pasta["pack_price"] = pasta["avg_price"] * pasta["pack_g"] / 1000
    pasta["units"] = pasta["value"] / pasta["pack_price"]
    pasta["short"] = (
        pasta["sku"]
        .str.replace(r"Knorr Pasta Pots\s+", "", regex=True)
        .str.replace(r"\s+\d+g$", "", regex=True)
    )
    pasta = pasta.sort_values("value", ascending=False)
    pasta["share"] = pasta["value"] / pasta["value"].sum()
    return pasta


def noodle_named(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["sku"].str.contains("noodle", case=False, na=False)].copy()


def set_run(run, text, size=12, bold=False, color=INK, font="Calibri"):
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = font


def add_text_box(slide, l, t, w, h, text, size=12, bold=False, color=INK, align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(l, t, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    set_run(p.add_run(), text, size=size, bold=bold, color=color)
    return box


def add_rect(slide, l, t, w, h, fill, line=None):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, l, t, w, h)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
    return shape


def disable_shadow(shape):
    sp_pr = shape._element.spPr
    effect = sp_pr.find(qn("a:effectLst"))
    if effect is not None:
        sp_pr.remove(effect)


def add_header(slide, title, subtitle):
    add_rect(slide, 0, 0, SLIDE_W, Inches(0.92), NAVY)
    add_text_box(
        slide,
        Inches(0.4),
        Inches(0.12),
        Inches(10.5),
        Inches(0.42),
        title,
        size=24,
        bold=True,
        color=WHITE,
    )
    add_text_box(
        slide,
        Inches(0.4),
        Inches(0.52),
        Inches(12.4),
        Inches(0.32),
        subtitle,
        size=12,
        color=RGBColor(0xC9, 0xD6, 0xE3),
    )
    add_rect(slide, 0, Inches(7.22), SLIDE_W, Inches(0.28), NAVY)
    add_text_box(
        slide,
        Inches(0.4),
        Inches(7.24),
        Inches(12.5),
        Inches(0.22),
        "Source: Monthly Time Groupings Export, South Africa  ·  Period in file: Jul 2025–Jun 2026  ·  Measures: 12mm CY Value, Volume, Ave Price (Value/Volume)",
        size=10,
        color=RGBColor(0xC9, 0xD6, 0xE3),
    )


def add_kpi(slide, l, t, w, h, label, value, note=None, accent=BLUE):
    card = add_rect(slide, l, t, w, h, LIGHT, LINE)
    disable_shadow(card)
    add_rect(slide, l, t, Inches(0.07), h, accent)
    add_text_box(slide, l + Inches(0.16), t + Inches(0.08), w - Inches(0.22), Inches(0.24), label, size=11, color=MUTED)
    add_text_box(slide, l + Inches(0.16), t + Inches(0.30), w - Inches(0.22), Inches(0.36), value, size=20, bold=True, color=NAVY)
    if note:
        add_text_box(slide, l + Inches(0.16), t + Inches(0.66), w - Inches(0.22), Inches(0.24), note, size=10, color=MUTED)


def add_table(slide, l, t, w, h, headers, rows, col_widths=None):
    table_shape = slide.shapes.add_table(len(rows) + 1, len(headers), l, t, w, h)
    table = table_shape.table
    if col_widths:
        for i, width in enumerate(col_widths):
            table.columns[i].width = width
    for i, header in enumerate(headers):
        cell = table.cell(0, i)
        cell.text = ""
        p = cell.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT if i == 0 else PP_ALIGN.RIGHT
        set_run(p.add_run(), header, size=11, bold=True, color=WHITE)
        cell.fill.solid()
        cell.fill.fore_color.rgb = NAVY
    for r, row in enumerate(rows, start=1):
        bg = LIGHT if r % 2 else WHITE
        for c, value in enumerate(row):
            cell = table.cell(r, c)
            cell.text = ""
            p = cell.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT if c == 0 else PP_ALIGN.RIGHT
            set_run(p.add_run(), str(value), size=12, bold=(c == 0), color=INK)
            cell.fill.solid()
            cell.fill.fore_color.rgb = bg
    return table


def pasta_chart(pasta: pd.DataFrame) -> Path:
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    path = CHART_DIR / "pasta_sku_value.png"
    labels = pasta["short"].tolist()
    values = (pasta["value"] / 1000).tolist()
    fig, ax = plt.subplots(figsize=(6.4, 2.6), dpi=180)
    colors = ["#1B4F8A", "#0E7C7B", "#C45C26"]
    bars = ax.barh(labels[::-1], values[::-1], color=colors[::-1], height=0.55)
    ax.set_xlabel("June 2026 value (R'000)")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax.tick_params(axis="both", labelsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#D5DBE0")
    ax.spines["bottom"].set_color("#D5DBE0")
    for bar, val in zip(bars, values[::-1]):
        ax.text(val + 8, bar.get_y() + bar.get_height() / 2, f"R{val:,.0f}k", va="center", fontsize=8, color="#1A1A1A")
    ax.set_xlim(0, max(values) * 1.22)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def soup_chart(chicken: pd.DataFrame) -> Path:
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    path = CHART_DIR / "chicken_noodle_soup.png"
    order = ["Mar 2026", "Apr 2026", "May 2026", "Jun 2026"]
    chicken = chicken.set_index("month").loc[order]
    fig, ax = plt.subplots(figsize=(6.2, 2.35), dpi=180)
    ax.plot(order, chicken["value"] / 1_000_000, marker="o", color="#1B4F8A", linewidth=2.2)
    ax.fill_between(range(len(order)), chicken["value"] / 1_000_000, color="#1B4F8A", alpha=0.08)
    ax.set_ylabel("Value (R m)")
    ax.set_ylim(0, 2.5)
    ax.tick_params(axis="both", labelsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for x, y in zip(order, chicken["value"] / 1_000_000):
        ax.text(x, y + 0.12, f"R{y:.2f}m", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def build():
    df = load_data()
    pasta = pasta_table(df)
    noodles = noodle_named(df)
    instant = noodles[noodles["category"] == "Instant Soup"]
    chicken = noodles[noodles["sku"].str.contains("Chicken Noodle", case=False)].copy()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    pasta_value = pasta["value"].sum()
    pasta_vol = pasta["volume"].sum()
    pasta_units = pasta["units"].sum()
    pasta_chart_path = pasta_chart(pasta)
    soup_chart_path = soup_chart(chicken)

    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    blank = prs.slide_layouts[6]

    # --- Slide 1: Pasta ---
    s1 = prs.slides.add_slide(blank)
    add_header(
        s1,
        "Pasta: Unilever snapshot (June 2026)",
        "Knorr Pasta Pots only  ·  No competitor manufacturers in this file  ·  Pasta does not appear in Jul 2025–May 2026",
    )
    add_kpi(s1, Inches(0.4), Inches(1.12), Inches(3.05), Inches(0.98), "VALUE", "R1.24m", "June 2026 only", BLUE)
    add_kpi(s1, Inches(3.60), Inches(1.12), Inches(3.05), Inches(0.98), "VOLUME", "1.57 tonnes", f"{pasta_units/1000:.1f}k pots", TEAL)
    add_kpi(s1, Inches(6.80), Inches(1.12), Inches(3.05), Inches(0.98), "PRICE POINT", "R49 / pot", "R779–832 / kg", ORANGE)
    add_kpi(s1, Inches(10.00), Inches(1.12), Inches(2.93), Inches(0.98), "PLAYERS IN FILE", "Knorr only", "Unilever, 3 SKUs", RED)

    rows = []
    for _, r in pasta.iterrows():
        rows.append(
            [
                r["short"],
                f"R{r['value']/1000:,.0f}k",
                f"{r['share']*100:.0f}%",
                f"{r['volume']:,.0f} kg",
                f"R{r['avg_price']:,.0f}",
                f"R{r['pack_price']:.2f}",
            ]
        )
    add_table(
        s1,
        Inches(0.4),
        Inches(2.28),
        Inches(7.55),
        Inches(2.15),
        ["SKU", "Value", "Share", "Volume", "R/kg", "R/pack"],
        rows,
        col_widths=[Inches(2.15), Inches(1.05), Inches(0.9), Inches(1.15), Inches(1.05), Inches(1.25)],
    )
    s1.shapes.add_picture(str(pasta_chart_path), Inches(8.15), Inches(2.28), Inches(4.75), Inches(2.15))

    takeaway = add_rect(s1, Inches(0.4), Inches(4.65), Inches(12.53), Inches(2.35), LIGHT, LINE)
    disable_shadow(takeaway)
    add_text_box(s1, Inches(0.58), Inches(4.78), Inches(12.1), Inches(0.28), "What this tells the client", size=14, bold=True, color=NAVY)
    bullets = [
        "Unilever’s Pasta line in this extract is one range at one price: Knorr Pasta Pots, all ~R49 a pot.",
        "Carbonara is the lead SKU (49% of value). Tomato & Mozzarella 30%. Mushroom 22% and the smallest pack (59g) at the highest R/kg.",
        "There is no 12-month Pasta view here. The SKUs only appear in June 2026, so we cannot say if the line is winning or losing.",
        "Key players and category share cannot be read from this file: every row is Manufacturer = Unilever.",
    ]
    box = s1.shapes.add_textbox(Inches(0.58), Inches(5.10), Inches(12.1), Inches(1.75))
    tf = box.text_frame
    tf.word_wrap = True
    for i, line in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.level = 0
        p.space_after = Pt(4)
        set_run(p.add_run(), "•  " + line, size=13, color=INK)
    s1.notes_slide.notes_text_frame.text = (
        f"Pasta June 2026 value R{pasta_value:,.0f}; volume {pasta_vol:,.1f} kg; "
        f"estimated {pasta_units:,.0f} pots. Price is value/volume, i.e. R/kg. "
        "Pack price = R/kg × pack weight."
    )

    # --- Slide 2: Noodles ---
    s2 = prs.slides.add_slide(blank)
    add_header(
        s2,
        "Noodles: this extract cannot answer the category question",
        "No Noodles category  ·  Instant noodle cups at R0  ·  Only live ‘Noodle’ SKU is a soup sachet",
    )

    add_rect(s2, Inches(0.4), Inches(1.12), Inches(6.15), Inches(2.55), LIGHT, LINE)
    add_text_box(s2, Inches(0.58), Inches(1.22), Inches(5.8), Inches(0.3), "What we looked for", size=14, bold=True, color=NAVY)
    box = s2.shapes.add_textbox(Inches(0.58), Inches(1.55), Inches(5.8), Inches(1.95))
    tf = box.text_frame
    tf.word_wrap = True
    for i, line in enumerate(
        [
            "Categories in file: 21 Unilever categories. Pasta is present. Noodles is not.",
            "Instant Soup: Knorr Cup A Snack Noodle (Smoked Paprika & Mung Bean; Spicy Bean) — listed in Jul, Aug, Mar with R0 / 0 kg.",
            "Regular & Low Price Soup: Knorr Soup Chicken Noodle 45g is the only SKU with ‘Noodle’ in the name and sales.",
        ]
    ):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(6)
        set_run(p.add_run(), "•  " + line, size=13, color=INK)

    add_rect(s2, Inches(6.75), Inches(1.12), Inches(6.18), Inches(2.55), LIGHT, LINE)
    add_text_box(s2, Inches(6.93), Inches(1.22), Inches(5.85), Inches(0.3), "Therefore we cannot say", size=14, bold=True, color=RED)
    box = s2.shapes.add_textbox(Inches(6.93), Inches(1.55), Inches(5.85), Inches(1.95))
    tf = box.text_frame
    tf.word_wrap = True
    for i, line in enumerate(
        [
            "Who the key Noodles players are (Tiger, Rainbow, Maggi, house brands, etc.).",
            "Who is winning or losing share over 12 months.",
            "What the Noodles price ladder looks like, or where Unilever sits on it.",
        ]
    ):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(8)
        set_run(p.add_run(), "•  " + line, size=13, color=INK)

    add_text_box(
        s2,
        Inches(0.4),
        Inches(3.80),
        Inches(12.5),
        Inches(0.3),
        "Closest live SKU — Knorr Soup Chicken Noodle 45g (soup category, not noodles)",
        size=14,
        bold=True,
        color=NAVY,
    )
    soup_rows = []
    for _, r in chicken.sort_values("month").iterrows():
        pack = r["avg_price"] * 45 / 1000
        soup_rows.append(
            [
                r["month"],
                f"R{r['value']/1000:,.0f}k",
                f"{r['volume']:,.0f} kg",
                f"R{r['avg_price']:,.1f}",
                f"R{pack:.2f}",
            ]
        )
    add_table(
        s2,
        Inches(0.4),
        Inches(4.15),
        Inches(6.3),
        Inches(2.15),
        ["Month", "Value", "Volume", "R/kg", "R/sachet"],
        soup_rows,
        col_widths=[Inches(1.4), Inches(1.2), Inches(1.25), Inches(1.15), Inches(1.3)],
    )
    s2.shapes.add_picture(str(soup_chart_path), Inches(6.95), Inches(4.15), Inches(5.95), Inches(2.15))
    s2.notes_slide.notes_text_frame.text = (
        "Do not present Chicken Noodle soup as the Noodles category. "
        f"Instant noodle cup rows: {len(instant)} months, all zero. "
        "Chicken Noodle soup value Mar–Jun: R0.66m → R1.01m → R1.29m → R2.12m."
    )

    # --- Slide 3: So what / data needed ---
    s3 = prs.slides.add_slide(blank)
    add_header(
        s3,
        "So what, and the extract we still need",
        "This file is a Unilever portfolio cut, not a Pasta / Noodles category competitive cut",
    )

    add_rect(s3, Inches(0.4), Inches(1.12), Inches(6.15), Inches(5.85), LIGHT, LINE)
    add_text_box(s3, Inches(0.58), Inches(1.24), Inches(5.8), Inches(0.32), "Working conclusions from this file", size=16, bold=True, color=NAVY)
    box = s3.shapes.add_textbox(Inches(0.58), Inches(1.65), Inches(5.8), Inches(5.05))
    tf = box.text_frame
    tf.word_wrap = True
    conclusions = [
        "Pasta: Unilever is in-market in June with three Pasta Pots at a single ~R49 price point. Carbonara is the SKU to watch inside that range.",
        "Noodles: Unilever’s instant noodle cups in this file have no sales. They look delisted or not distributed, not competing.",
        "Do not use Chicken Noodle soup as a proxy for the Noodles category. It is a 45g soup sachet at ~R6.",
        "Winning / losing vs competitors cannot be scored. There are no non-Unilever rows.",
        "Price architecture for the category cannot be scored. We only have Unilever’s own R/kg.",
    ]
    for i, line in enumerate(conclusions):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(12)
        set_run(p.add_run(), "•  " + line, size=14, color=INK)

    add_rect(s3, Inches(6.75), Inches(1.12), Inches(6.18), Inches(5.85), NAVY)
    add_text_box(s3, Inches(6.95), Inches(1.24), Inches(5.8), Inches(0.32), "Please pull this instead", size=16, bold=True, color=WHITE)
    box = s3.shapes.add_textbox(Inches(6.95), Inches(1.70), Inches(5.8), Inches(4.9))
    tf = box.text_frame
    tf.word_wrap = True
    need = [
        "Market: South Africa, same source.",
        "Time: monthly, Jul 2025–Jun 2026 (plus June 2026 latest month).",
        "Filter: Category = Pasta and Category = Noodles (or the local subcategory split).",
        "Rows: all manufacturers and brands, not Unilever only.",
        "Columns: month, category, manufacturer, brand, SKU, value, volume, average price, pack size.",
        "Then we can show: category size, key players, 12-month winners/losers, and the price ladder with Unilever SKUs marked.",
    ]
    for i, line in enumerate(need):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(10)
        run = p.add_run()
        set_run(run, "•  " + line, size=14, color=WHITE)

    s3.notes_slide.notes_text_frame.text = (
        "Ask the analyst / Nielsen owner for a category extract, not a Unilever brand extract. "
        "Same 12mm monthly grouping is fine if all manufacturers are included."
    )

    prs.save(DECK)
    print(f"Wrote {DECK}")
    print(f"Pasta value {pasta_value:,.2f} volume {pasta_vol:,.2f} units {pasta_units:,.0f}")
    print(f"Instant noodle rows {len(instant)} all zero={ (instant['value']==0).all() }")
    print(chicken[["month", "value", "volume", "avg_price"]].to_string(index=False))


if __name__ == "__main__":
    build()
