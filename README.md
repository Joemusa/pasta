# FMCG Commercial Intelligence System

Sprint 1 delivers a **deterministic Data QA Agent**. It inspects uploaded POS CSV/Excel files, maps columns onto a canonical commercial schema, standardises types, validates quality, flags outliers without deleting them, and writes a structured QA report plus a cleaned dataset for downstream agents.

The agent never uses an LLM to decide whether data is valid. Future agents (Distribution, Price, Promotion, and others) are not implemented in this sprint; the QA report exposes explicit capability flags they will consume.

## Layout

```
backend/
  agents/data_qa/     # load, map, standardise, validate, outliers, capabilities
  schemas/            # canonical fields, aliases, QA thresholds
  tests/
  data/
    raw/              # preserved originals (never overwritten)
    clean/            # standardised commercial tables
    qa_reports/       # structured JSON reports
```

## Install

```bash
python3 -m pip install -r requirements.txt
```

Python 3.11+ is required.

## Run

From the repository root:

```bash
python3 -m backend.agents.data_qa backend/data/raw/sample_pos.csv
```

Useful flags:

```bash
python3 -m backend.agents.data_qa path/to/file.xlsx \
  --data-root backend/data \
  --config backend/schemas/qa_config.yaml \
  --aliases backend/schemas/canonical_schema.yaml
```

- Raw files are copied into `backend/data/raw/` when the source lives elsewhere. Existing raw copies and the original upload are never overwritten.
- Clean output: `backend/data/clean/<stem>.clean.csv`
- QA report: `backend/data/qa_reports/<stem>.qa.json`
- Exit code `1` means `FAIL`; `0` means the file is usable (`PASS`, `PASS_WITH_WARNINGS`, or `PARTIAL_PASS`).

## Tests

```bash
python3 -m pytest
```

## Canonical schema

Core dimensions: `date`, `manufacturer`, `brand`, `product`, `sku`, `retailer`, `region`

Core metrics: `sales_value`, `sales_volume`, `store_count`

Price: `current_price`, `normal_price`

Promotion: `percent_time_on_promo`, `percent_sales_on_promo`, `promotion_flag`

Alternative source names are mapped in `backend/schemas/canonical_schema.yaml`. Retailer, product, and manufacturer aliases are data, not code — edit that YAML (or pass `--aliases`) instead of changing the agent.

If a file is a single-banner extract with no retailer column, inject it via config rather than hard-coding a banner:

```yaml
constant_columns:
  retailer: National multi-retailer panel
```

## What the agent checks

**Critical (typically `FAIL`):** unreadable file, no valid dates, missing product/SKU, missing retailer, missing sales value/volume, unsafe conflicting duplicates, invalid date parsing above threshold.

**Warnings:** missing region / manufacturer / promotion / price / normal price / store count, zero sales, sparse history, outliers, safe duplicate drops, negative sales or store counts (those rows are excluded), unpopulated metric slots.

**Validity:** non-negative sales and store counts; prices `> 0` where present; percentages in `0–100` after auto-detecting a `0–1` vs `0–100` source scale; valid dates; empty strings become null.

`PARTIAL_PASS` is based on the share of **populated** rows dropped as invalid. Empty Nielsen-style week slots are recorded and excluded, but they do not by themselves force `PARTIAL_PASS` or collapse the quality score.

Outliers are flagged with MAD (IQR fallback) **within each product series** when a product column exists, so mixed SKU grains are not compared as one population. They are not deleted.

Date fields `date_min` / `date_max` / `distinct_dates` describe the **clean** table. `source_date_*` fields describe the full mapped extract, including empty slots.

## Status and downstream capabilities

| Status | Meaning |
| --- | --- |
| `PASS` | Required fields present, no issues |
| `PASS_WITH_WARNINGS` | Analysis-ready, with warnings |
| `PARTIAL_PASS` | Analysis-ready after dropping a material share of **populated** invalid rows |
| `FAIL` | Basic commercial analysis cannot run |

The JSON report always includes:

```json
{
  "status": "PASS_WITH_WARNINGS",
  "analysis_ready": true,
  "quality_score": 92,
  "critical_issues": [],
  "warnings": [],
  "capabilities": {
    "distribution": true,
    "price": true,
    "promotion": true,
    "macro_overlay": true,
    "social_evidence": true,
    "commercial_brain": true
  }
}
```

Capability rules (evaluated on the cleaned table):

- **distribution** — `store_count` present
- **price** — `current_price` or `normal_price`, plus enough distinct dates
- **promotion** — promo percent or flag, plus enough distinct dates
- **macro_overlay** — at least one valid date
- **social_evidence** — brand or product present
- **commercial_brain** — `analysis_ready` (date, product or sku, retailer, sales value, sales volume)

Thresholds live in `backend/schemas/qa_config.yaml`.

## Sample outputs

- Input: `backend/data/raw/sample_pos.csv`
- Clean: `backend/data/clean/sample_pos.clean.csv`
- Report: `backend/data/qa_reports/sample_pos.qa.json`
