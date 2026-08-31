"""Shared loading of listening reports without inventing observations."""

from __future__ import annotations

from pathlib import Path

from backend.agents.social_common.models import DataMode, SpecialistReport
from backend.agents.social_common.paths import SocialLoadError


def report_dir(root: Path, data_mode: DataMode) -> Path:
    folder = "social_fixture_reports" if data_mode == "TEST_FIXTURES_ONLY" else "social_reports"
    return root / folder


def discover_listening_path(root: Path, *, prefer_fixtures: bool = False) -> Path | None:
    live = root / "social_reports" / "social_listening_v1.json"
    fixtures = root / "social_fixture_reports" / "social_listening_v1.json"
    if prefer_fixtures and fixtures.is_file():
        return fixtures
    if live.is_file():
        return live
    if fixtures.is_file():
        return fixtures
    return None


def ensure_listening(
    root: Path,
    *,
    listening: SpecialistReport | None = None,
    fixture_path: str | Path | None = None,
    write_outputs: bool = True,
) -> SpecialistReport:
    if listening is not None:
        return listening
    from backend.agents.social_listening.agent import load_listening_report, run_social_listening

    if fixture_path is not None:
        return run_social_listening(root, fixture_path=fixture_path, write_outputs=write_outputs)
    found = discover_listening_path(root, prefer_fixtures=False)
    if found is not None:
        return load_listening_report(found)
    return run_social_listening(root, write_outputs=write_outputs)


def require_listening(root: Path) -> SpecialistReport:
    found = discover_listening_path(root)
    if found is None:
        raise SocialLoadError("Social listening report not found. Run SocialListeningAgent first.")
    from backend.agents.social_listening.agent import load_listening_report

    return load_listening_report(found)
