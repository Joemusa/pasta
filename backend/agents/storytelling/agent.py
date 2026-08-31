"""Storytelling Engine V1: Commercial Brain one-slide → executive FMCG story."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from backend.agents.storytelling.loader import _display, discover_brain_slide
from backend.agents.storytelling.macro import attach_macro_context, discover_macro_pack, parse_macro_pack
from backend.agents.storytelling.models import StorytellingReport, StorytellingStatus, absent_macro_context
from backend.agents.storytelling.narrative import assert_no_unsupported_claims, build_story

logger = logging.getLogger("backend.agents.storytelling")

ONE_SLIDE_FILENAME = "storytelling_v1_one_slide.json"


def _configure_logging() -> None:
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def run_storytelling(
    input_path: str | Path,
    *,
    write_outputs: bool = True,
) -> StorytellingReport:
    _configure_logging()
    source = Path(input_path).expanduser().resolve()
    logger.info("storytelling_start input=%s", source)
    slide, source_file = discover_brain_slide(source)
    story = build_story(slide)
    pack, macro_file = discover_macro_pack(source)
    if pack is not None and macro_file is not None:
        story = attach_macro_context(story, parse_macro_pack(pack, macro_file))
        source_macro = _display(macro_file)
    else:
        story = attach_macro_context(story, absent_macro_context())
        source_macro = None
    assert_no_unsupported_claims(story)
    status = StorytellingStatus.READY_WITH_WARNINGS
    report = StorytellingReport(
        status=status,
        source_brain_slide=_display(source_file),
        source_macro_pack=source_macro,
        input_path=_display(source),
        one_slide=story,
    )
    if write_outputs:
        if source.is_dir():
            out_dir = source / "storytelling_reports"
        elif source.parent.name == "brain_reports":
            out_dir = source.parent.parent / "storytelling_reports"
        else:
            out_dir = source.parent / "storytelling_reports"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / ONE_SLIDE_FILENAME
        payload = story.model_dump(mode="json")
        out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        report.report_output_path = _display(out_path)
        logger.info("storytelling_written path=%s headline=%s", out_path, story.headline)
    return report
