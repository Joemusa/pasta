#!/usr/bin/env python3
"""Build the Pasta / Noodles review: Smollan title + thank-you only; original data visuals in between."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pymupdf
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

from build_deck import analyse, fmt_pct, fmt_pp, fmt_r, load

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PDF = ROOT / "templates" / "Smollan_Unilever_Template.pdf"
ASSETS = ROOT / "output" / "template_assets"
CHART_DIR = ROOT / "output" / "charts"
DECK = ROOT / "output" / "Unilever_Pasta_Noodles_Jun2026.pptx"

NAVY = RGBColor(0x12, 0x2A, 0x4A)
BLUE = RGBColor(0x1F, 0x5F, 0xA8)
ORANGE = RGBColor(0xD0, 0x5A, 0x1A)
RED = RGBColor(0xB0, 0x28, 0x28)
GREEN = RGBColor(0x1B, 0x7A, 0x3A)
INK = RGBColor(0x11, 0x11, 0x11)
MUTED = RGBColor(0x3D, 0x4A, 0x55)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT = RGBColor(0xF3, 0xF5, 0xF7)
LINE = RGBColor(0xC8, 0xD0, 0xD8)
ROW_ALT = RGBColor(0xEE, 0xF2, 0xF6)
LIME = RGBColor(0x88, 0xC0, 0x40)
CYAN = RGBColor(0x00, 0xB8, 0xF0)

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)
FONT = "Calibri"


def extract_assets() -> dict[str, Path]:
    ASSETS.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(TEMPLATE_PDF)
    mapping = {
        "title_bg": (0, 11),
        "logo_white_raw": (0, 13),
        "thanks_bg": (12, 125),
    }
    paths = {}
    for name, (_page, xref) in mapping.items():
        pix = pymupdf.Pixmap(doc, xref)
        if pix.n - pix.alpha > 3:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        path = ASSETS / f"{name}.png"
        pix.save(str(path))
        paths[name] = path

    raw = Image.open(paths["logo_white_raw"]).convert("RGBA")
    arr = np.array(raw)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    mask = (r.astype(int) + g.astype(int) + b.astype(int)) < 84
    arr[:, :, 3] = np.where(mask, 0, 255)
    im = Image.fromarray(arr)
    ys, xs = np.where(arr[:, :, 3] > 10)
    crop = im.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
    logo = ASSETS / "logo_white.png"
    crop.save(logo)
    paths["logo_white"] = logo
    return paths


def set_run(run, text, size=14, bold=False, color=INK):
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = FONT


def add_text(slide, l, t, w, h, text, size=14, bold=False, color=INK, align=PP_ALIGN.LEFT):
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
        shape.line.width = Pt(1)
    sp_pr = shape._element.spPr
    effect = sp_pr.find(qn("a:effectLst"))
    if effect is not None:
        sp_pr.remove(effect)
    return shape


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
        set_run(p.add_run(), header, size=13, bold=True, color=WHITE)
        cell.fill.solid()
        cell.fill.fore_color.rgb = NAVY
    for r, row in enumerate(rows, start=1):
        bg = ROW_ALT if r % 2 else WHITE
        for c, value in enumerate(row):
            cell = table.cell(r, c)
            cell.text = ""
            p = cell.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT if c == 0 else PP_ALIGN.RIGHT
            text = str(value)
            color = INK
            if c > 0 and text.startswith("+"):
                color = GREEN
            elif c > 0 and text.startswith("-"):
                color = RED
            set_run(p.add_run(), text, size=13, bold=(c == 0), color=color)
            cell.fill.solid()
            cell.fill.fore_color.rgb = bg
    return table


LOGO_CONTENT = ROOT / "templates" / "smollan_logo_content.png"


def content_shell(slide, title, page_no, total=6):
    add_rect(slide, 0, 0, SLIDE_W, SLIDE_H, WHITE)
    add_rect(slide, 0, 0, Inches(0.12), SLIDE_H, NAVY)
    add_rect(slide, 0, 0, SLIDE_W, Inches(0.08), NAVY)
    add_text(slide, Inches(0.38), Inches(0.18), Inches(10.4), Inches(0.46), title, size=24, bold=True, color=NAVY)
    add_rect(slide, Inches(0.38), Inches(0.66), Inches(2.2), Inches(0.06), ORANGE)
    slide.shapes.add_picture(str(LOGO_CONTENT), Inches(11.05), Inches(0.14), Inches(1.95), Inches(0.42))
    add_rect(slide, 0, Inches(7.18), SLIDE_W, Inches(0.32), LIGHT)
    add_text(
        slide,
        Inches(0.38),
        Inches(7.22),
        Inches(9.2),
        Inches(0.22),
        "South Africa Pasta  ·  12 months Jul 25–Jun 26 vs YA  ·  latest month Jun 26  ·  price = value ÷ volume",
        size=11,
        color=MUTED,
    )
    add_text(slide, Inches(11.4), Inches(7.22), Inches(1.55), Inches(0.22), f"{page_no} / {total}", size=11, bold=True, color=NAVY, align=PP_ALIGN.RIGHT)


def kpi(slide, l, t, w, h, label, value, note, accent=BLUE):
    add_rect(slide, l, t, w, h, LIGHT, LINE)
    add_rect(slide, l, t, Inches(0.09), h, accent)
    add_text(slide, l + Inches(0.20), t + Inches(0.08), w - Inches(0.28), Inches(0.24), label.upper(), size=11, bold=True, color=MUTED)
    add_text(slide, l + Inches(0.20), t + Inches(0.32), w - Inches(0.28), Inches(0.40), value, size=24, bold=True, color=NAVY)
    add_text(slide, l + Inches(0.20), t + Inches(0.72), w - Inches(0.28), Inches(0.28), note, size=12, color=INK)


def add_chart(slide, path, left, top, width):
    """Place a chart by width only so labels are not stretched."""
    return slide.shapes.add_picture(str(path), left, top, width=width)


def barh(labels, values, path, xlabel, colors, fmt, label_size=13):
    n = max(len(labels), 1)
    fig_w, fig_h = 7.6, max(3.5, 0.58 * n + 1.40)
    plt.rcParams.update({"font.size": label_size, "font.family": "DejaVu Sans"})
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=200)
    y = np.arange(n)
    ax.barh(y, list(reversed(values)), color=list(reversed(colors)), height=0.62, zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels(list(reversed(labels)))
    ax.set_xlabel(xlabel, fontsize=label_size, color="#111111", labelpad=10)
    ax.tick_params(axis="x", labelsize=label_size, colors="#111111", pad=4)
    ax.tick_params(axis="y", labelsize=label_size, colors="#111111", pad=10, length=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#C8D0D8")
    ax.spines["bottom"].set_color("#C8D0D8")
    ax.grid(axis="x", color="#EEF2F6", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.margins(y=0.10)
    xmax = max(values) * 1.30 if values else 1
    ax.set_xlim(0, xmax)
    for bar, val in zip(ax.patches, reversed(values)):
        ax.text(
            val + xmax * 0.02,
            bar.get_y() + bar.get_height() / 2,
            fmt(val),
            va="center",
            ha="left",
            fontsize=label_size,
            color="#111111",
            fontweight="bold",
            clip_on=False,
        )
    fig.tight_layout(pad=0.40)
    fig.savefig(path, facecolor="white", bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)


def build():
    assets = extract_assets()
    a = analyse(load())
    CHART_DIR.mkdir(parents=True, exist_ok=True)

    sub = a["sub"].sort_values("share_mat", ascending=False)
    rename = {"Pasta Miscellaneous": "Other pasta"}
    major = sub[sub["share_mat"] >= 5]
    minor = sub[sub["share_mat"] < 5]
    sub_labels = [rename.get(i, i) for i in major.index]
    sub_vals = major["share_mat"].tolist()
    if len(minor):
        sub_labels.append("Other pasta")
        sub_vals.append(float(minor["share_mat"].sum()))
    sub_colors = ["#122A4A", "#1F5FA8", "#D05A1A", "#5A6A78"]
    barh(
        sub_labels,
        sub_vals,
        CHART_DIR / "data_subcat.png",
        "12-month Pasta value share (%)",
        sub_colors[: len(sub_labels)],
        lambda v: f"{v:.0f}%",
        label_size=14,
    )
    brands = a["n_brand"].head(6)
    barh(
        brands.index.tolist(),
        brands["share_mat"].tolist(),
        CHART_DIR / "data_brands.png",
        "12-month Noodles value share (%)",
        ["#1F5FA8" if pp >= 0 else "#B02828" for pp in brands["pp"]],
        lambda v: f"{v:.0f}%",
        label_size=14,
    )
    ladder = a["ladder"]
    barh(
        ladder.index.tolist(),
        ladder["pack_price"].tolist(),
        CHART_DIR / "data_price.png",
        "Typical unit pack price (R)",
        ["#D05A1A" if b == "Knorr" else "#1F5FA8" for b in ladder.index],
        lambda v: f"R{v:.2f}",
        label_size=14,
    )

    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    blank = prs.slide_layouts[6]

    # 1. Title — template slide 1
    s = prs.slides.add_slide(blank)
    s.shapes.add_picture(str(assets["title_bg"]), 0, 0, SLIDE_W, SLIDE_H)
    s.shapes.add_picture(str(assets["logo_white"]), Inches(0.42), Inches(0.42), Inches(2.55), Inches(0.78))
    add_text(s, Inches(0.45), Inches(2.28), Inches(6.5), Inches(0.80), "Unilever Presentation", size=36, bold=True, color=WHITE)
    add_text(s, Inches(0.45), Inches(3.10), Inches(6.5), Inches(0.40), "Pasta & Noodles Category Review", size=20, bold=True, color=WHITE)
    add_text(s, Inches(0.45), Inches(3.52), Inches(6.5), Inches(0.34), "South Africa  |  12 months to June 2026", size=16, color=CYAN)
    add_text(s, Inches(0.45), Inches(6.50), Inches(6.0), Inches(0.30), "Updated: 18/08/2026", size=14, bold=True, color=LIME)
    add_text(s, Inches(0.45), Inches(7.10), Inches(6.0), Inches(0.24), "A SMOLLAN COMPANY", size=12, color=WHITE)

    # 2. Pasta
    s = prs.slides.add_slide(blank)
    content_shell(s, "Pasta: 12-month view to June 2026", 2)
    kpi(s, Inches(0.38), Inches(0.88), Inches(3.10), Inches(1.08), "12-month value", fmt_r(a["pasta_mat"]["value"]), f"{fmt_pct(a['pasta_g']['value'])} value  ·  vol {fmt_pct(a['pasta_g']['volume'])}", BLUE)
    kpi(s, Inches(3.58), Inches(0.88), Inches(3.10), Inches(1.08), "June 2026", fmt_r(a["pasta_jun"]["value"]), f"{fmt_pct(a['pasta_jun_g']['value'])} vs Jun 25", RGBColor(0x0E, 0x7C, 0x7B))
    kpi(s, Inches(6.78), Inches(0.88), Inches(3.10), Inches(1.08), "Noodles share", f"{a['n_share_pasta']*100:.0f}% of Pasta", f"{fmt_pp((a['n_share_pasta']-a['n_share_pasta_ya'])*100)} vs YA", ORANGE)
    kpi(s, Inches(9.98), Inches(0.88), Inches(2.96), Inches(1.08), "Category price", f"R{a['pasta_mat']['price']:.0f}/kg", f"Noodles R{a['n_mat']['price']:.0f}  ·  dry ~R32–35", RED)

    add_text(s, Inches(0.38), Inches(2.12), Inches(6.3), Inches(0.28), "Where the value sits", size=16, bold=True, color=NAVY)
    add_chart(s, CHART_DIR / "data_subcat.png", Inches(0.28), Inches(2.42), Inches(6.40))

    add_text(s, Inches(6.90), Inches(2.12), Inches(6.0), Inches(0.28), "Key players — winning and losing", size=16, bold=True, color=NAVY)
    mfr_rows = []
    labels = {
        "Zhejiang Green Home Food Co., Ltd.": "Roka",
        "Pastificio Fabianelli": "Fabianelli",
        "Unknown Manufacturer": "Unknown",
    }
    for name, r in a["pasta_mfr"].head(7).iterrows():
        mfr_rows.append(
            [
                labels.get(name, name),
                f"{r['share_mat']:.1f}%",
                fmt_pp(r["pp"]),
                fmt_pct(r["val_chg"]),
                f"R{r['price_mat']:.0f}",
            ]
        )
    add_table(
        s,
        Inches(6.90),
        Inches(2.42),
        Inches(6.05),
        Inches(3.35),
        ["Manufacturer", "Share", "vs YA", "Value", "R/kg"],
        mfr_rows,
        col_widths=[Inches(1.85), Inches(1.00), Inches(1.00), Inches(1.10), Inches(1.10)],
    )
    add_text(
        s,
        Inches(0.38),
        Inches(6.10),
        Inches(12.55),
        Inches(0.95),
        "Noodles is the Pasta category (64% of value, growing faster than dry pasta). Kellogg's and Indomie are taking share. Nestlé, Mr Pasta and Tiger Brands are losing it. Unilever does not appear in Pasta until Noodles, and only in June.",
        size=15,
        color=INK,
    )

    # 3. Noodles players
    s = prs.slides.add_slide(blank)
    content_shell(s, "Noodles: who is winning and losing", 3)
    kpi(s, Inches(0.38), Inches(0.86), Inches(3.10), Inches(0.96), "12-month value", fmt_r(a["n_mat"]["value"]), f"{fmt_pct(a['n_g']['value'])}  ·  vol {fmt_pct(a['n_g']['volume'])}", BLUE)
    kpi(s, Inches(3.58), Inches(0.86), Inches(3.10), Inches(0.96), "June 2026", fmt_r(a["n_jun"]["value"]), f"{fmt_pct(a['n_jun_g']['value'])} vs Jun 25", RGBColor(0x0E, 0x7C, 0x7B))
    kpi(s, Inches(6.78), Inches(0.86), Inches(3.10), Inches(0.96), "Mass price", "R5–8 sachet", f"{a['sachet_share']*100:.0f}% of noodles value", ORANGE)
    kpi(s, Inches(9.98), Inches(0.86), Inches(2.96), Inches(0.96), "Unilever (Jun)", f"{a['u_share_n_jun']*100:.2f}% share", f"R{a['u_jun']['value'].sum()/1e6:.2f}m  ·  3 Pasta Pots", RED)

    add_text(s, Inches(0.38), Inches(1.96), Inches(6.3), Inches(0.26), "12-month Noodles value share", size=16, bold=True, color=NAVY)
    add_chart(s, CHART_DIR / "data_brands.png", Inches(0.22), Inches(2.24), Inches(6.50))

    rows = []
    for name in ["Kellogg's", "Maggi", "Indomie", "Roka", "Samyang", "Knorr"]:
        if name not in a["n_brand"].index:
            continue
        r = a["n_brand"].loc[name]
        jun = a["n_jun_brand"].loc[name, "share"] if name in a["n_jun_brand"].index else 0
        rows.append([name, f"{r['share_mat']:.1f}%", f"{jun:.1f}%", fmt_pp(r["pp"]), fmt_pct(r["val_chg"]), f"R{r['price_mat']:.0f}"])
    add_text(s, Inches(6.80), Inches(1.96), Inches(6.1), Inches(0.26), "12-month vs June scorecard", size=16, bold=True, color=NAVY)
    add_table(
        s,
        Inches(6.80),
        Inches(2.24),
        Inches(6.15),
        Inches(4.55),
        ["Brand", "12m", "Jun", "vs YA", "Value", "R/kg"],
        rows,
        col_widths=[Inches(1.35), Inches(0.85), Inches(0.85), Inches(0.95), Inches(1.05), Inches(1.10)],
    )

    # 4. Price + Unilever
    s = prs.slides.add_slide(blank)
    content_shell(s, "Noodles price point — and where Unilever sits", 4)
    add_text(s, Inches(0.38), Inches(0.86), Inches(6.4), Inches(0.28), "Typical unit pack price", size=16, bold=True, color=NAVY)
    add_chart(s, CHART_DIR / "data_price.png", Inches(0.22), Inches(1.16), Inches(6.55))
    add_text(
        s,
        Inches(0.38),
        Inches(5.52),
        Inches(6.4),
        Inches(0.55),
        "Typical unit = volume-weighted R/kg × pack size. Sachets sit at R5.88–R7.90. Knorr is ~8× that.",
        size=13,
        color=INK,
    )

    add_text(s, Inches(6.90), Inches(0.86), Inches(6.05), Inches(0.28), "Unilever SKUs — June 2026 only", size=16, bold=True, color=NAVY)
    add_rect(s, Inches(6.90), Inches(1.20), Inches(6.05), Inches(1.55), LIGHT, LINE)
    add_rect(s, Inches(6.90), Inches(1.20), Inches(0.09), Inches(1.55), ORANGE)
    add_text(s, Inches(7.16), Inches(1.30), Inches(5.60), Inches(0.32), "Pasta Pots are not a sachet", size=16, bold=True, color=NAVY)
    add_text(
        s,
        Inches(7.16),
        Inches(1.64),
        Inches(5.60),
        Inches(0.98),
        f"{a['sachet_share']*100:.0f}% of noodles value is R5–8 a pack. Knorr Pasta Pots are R49 a pot / ~R790/kg, 0.56% of Noodles in June (R{a['u_jun']['value'].sum()/1e6:.2f}m). Hold R49; do not promo into the R6 band.",
        size=14,
        color=INK,
    )
    u_rows = []
    for _, r in a["u_jun"].sort_values("value", ascending=False).iterrows():
        u_rows.append([r["short"], f"R{r['value']/1000:.0f}k", f"{r['share']*100:.0f}%", f"R{r['pack_price']:.2f}"])
    add_table(
        s,
        Inches(6.90),
        Inches(2.92),
        Inches(6.05),
        Inches(2.15),
        ["SKU", "Value", "Mix", "R/pot"],
        u_rows,
        col_widths=[Inches(2.35), Inches(1.15), Inches(1.15), Inches(1.40)],
    )
    add_text(
        s,
        Inches(6.90),
        Inches(5.22),
        Inches(6.05),
        Inches(1.70),
        "Not in the file before June. Carbonara is 49% of the line. The three SKUs compete with each other first. Samyang (~R39) is the nearer competitor, not Maggi or Kellogg's.",
        size=14,
        color=INK,
    )

    # 5. So what
    s = prs.slides.add_slide(blank)
    content_shell(s, "So what: Unilever is not in the sachet game", 5)
    points = [
        (
            "1",
            "Noodles runs Pasta",
            f"Noodles is {a['n_share_pasta']*100:.0f}% of Pasta value and growing {fmt_pct(a['n_g']['value'])}. Dry pasta (Tiger, private label, Mr Pasta at ~R32–35/kg) is a different business. Unilever is absent there.",
        ),
        (
            "2",
            "Kellogg's is winning, Maggi is losing",
            "Kellogg's 46% of Noodles (+2.0pp). Maggi 29% (−5.1pp). Indomie and Samyang are the other gainers. That is the competitive frame, not Knorr vs Maggi on the same pack.",
        ),
        (
            "3",
            "The category price point is ~R6",
            f"{a['sachet_share']*100:.0f}% of noodles value is a R5–8 sachet (Roka R5.88, Kellogg's R6.09, Maggi R6.79, Indomie R7.90). Samyang sits at ~R39 as a ramen/cup play.",
        ),
        (
            "4",
            "Pasta Pots are a different occasion",
            f"Knorr Pasta Pots appear only in June: R{a['u_jun']['value'].sum()/1e6:.2f}m, 0.56% of Noodles, ~R49 a pot / ~R790/kg — about 8× the mass sachet. Carbonara is 49% of the line. The three SKUs compete with each other first. Hold R49; do not promo into the R6 band.",
        ),
    ]
    y = Inches(0.92)
    for num, head, body in points:
        add_rect(s, Inches(0.38), y, Inches(12.55), Inches(1.38), LIGHT, LINE)
        add_rect(s, Inches(0.38), y, Inches(0.70), Inches(1.38), NAVY)
        add_text(s, Inches(0.38), y + Inches(0.40), Inches(0.70), Inches(0.50), num, size=24, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
        add_text(s, Inches(1.28), y + Inches(0.12), Inches(11.4), Inches(0.36), head, size=18, bold=True, color=NAVY)
        add_text(s, Inches(1.28), y + Inches(0.50), Inches(11.4), Inches(0.78), body, size=15, color=INK)
        y = Inches(y.inches + 1.50)

    # 6. Thank you — template last slide
    s = prs.slides.add_slide(blank)
    s.shapes.add_picture(str(assets["thanks_bg"]), 0, 0, SLIDE_W, SLIDE_H)
    s.shapes.add_picture(str(assets["logo_white"]), Inches(0.38), Inches(0.28), Inches(2.05), Inches(0.62))
    add_text(s, Inches(7.15), Inches(2.80), Inches(5.6), Inches(0.70), "Thank You!", size=40, bold=True, color=WHITE)
    add_rect(s, Inches(7.15), Inches(3.55), Inches(2.8), Inches(0.035), RGBColor(0x7A, 0x9A, 0xB8))
    add_text(s, Inches(7.15), Inches(3.70), Inches(5.6), Inches(0.40), "Joseph Hlongwane", size=20, bold=True, color=LIME)
    add_text(s, Inches(0.40), Inches(7.10), Inches(5.5), Inches(0.24), "A SMOLLAN COMPANY", size=12, color=WHITE)

    prs.save(DECK)
    print(f"Wrote {DECK}  slides={len(prs.slides)}")


if __name__ == "__main__":
    build()
