"""Configurable social search queries. Brand/category lists come from taxonomy YAML, not agent if-blocks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from backend.agents.social_common.models import SCHEMA_DIR
from backend.agents.social_common.taxonomy import load_taxonomy

DEFAULT_QUERIES_PATH = SCHEMA_DIR / "social_queries.yaml"


@dataclass(frozen=True)
class SearchQuery:
    query_id: str
    query_type: str
    text: str
    term: str | None = None


def load_query_spec(path: Path | None = None) -> dict[str, Any]:
    target = path or DEFAULT_QUERIES_PATH
    payload = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Query spec {target} is not a mapping")
    return payload


def _taxonomy_names(taxonomy: dict[str, Any], key: str) -> list[str]:
    block = taxonomy.get(key) or {}
    if isinstance(block, dict):
        return [str(name) for name in block.keys()]
    return []


def expand_search_queries(
    spec: dict[str, Any] | None = None,
    taxonomy: dict[str, Any] | None = None,
    *,
    source: str | None = None,
) -> list[SearchQuery]:
    spec = spec if spec is not None else load_query_spec()
    taxonomy = taxonomy if taxonomy is not None else load_taxonomy()
    built: list[SearchQuery] = []
    seen: set[str] = set()
    for row in spec.get("social_queries") or []:
        if not isinstance(row, dict):
            continue
        query_id = str(row.get("id") or row.get("type") or "query")
        query_type = str(row.get("type") or query_id)
        template = str(row.get("template") or "{name}")
        terms: list[str] = []
        tax_key = row.get("from_taxonomy")
        if tax_key:
            terms.extend(_taxonomy_names(taxonomy, str(tax_key)))
        terms.extend(str(item) for item in (row.get("terms") or []) if item)
        max_expand = int(row.get("max_expand") or len(terms) or 1)
        if not terms:
            terms = [""]
        for term in terms[:max_expand]:
            text = template.format(name=term).strip()
            if not text:
                continue
            key = f"{query_type}:{text.casefold()}"
            if key in seen:
                continue
            seen.add(key)
            built.append(SearchQuery(query_id=query_id, query_type=query_type, text=text, term=term or None))
    boosted = _south_africa_boost(built, spec, source)
    limit = int(spec.get("max_queries_per_source") or len(boosted))
    return boosted[:limit]


def _south_africa_boost(queries: list[SearchQuery], spec: dict[str, Any], source: str | None) -> list[SearchQuery]:
    geo = spec.get("south_africa") or {}
    boosts = geo.get("query_boosts") or {}
    phrases = list(boosts.get(source) or []) if source else []
    extra: list[SearchQuery] = []
    seen = {item.text.casefold() for item in queries}
    for item in queries[: int(geo.get("boost_first_n") or 3)]:
        for phrase in phrases:
            if not isinstance(phrase, str) or not phrase.strip():
                continue
            text = f"{item.text} {phrase.strip()}".strip()
            if text.casefold() in seen:
                continue
            seen.add(text.casefold())
            extra.append(
                SearchQuery(
                    query_id=f"{item.query_id}_za",
                    query_type=item.query_type,
                    text=text,
                    term=item.term,
                )
            )
    return extra + queries


def user_agent(spec: dict[str, Any] | None = None) -> str:
    spec = spec if spec is not None else load_query_spec()
    return str(spec.get("user_agent") or "UnileverPastaSocialIntelligence/1.0")
