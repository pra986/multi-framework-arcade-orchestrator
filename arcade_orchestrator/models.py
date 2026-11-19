from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class WorkerTaskSpec(BaseModel):
    """Specification for an isolated framework worker task."""

    game_id: str
    title: str
    framework: Literal["strands", "pydantic-ai", "maf", "agno", "mastra"]
    target_language: str
    prompt: str
    timeout_seconds: float = 30.0
    worker_cmd: list[str] = Field(default_factory=list)


class GameQAVerdict(BaseModel):
    """Structured Playwright QA verdict for a generated mini-app."""

    game_id: str
    passed: bool
    has_index_html: bool = False
    has_game_js: bool = False
    console_errors: list[str] = Field(default_factory=list)
    missing_assets: list[str] = Field(default_factory=list)
    notes: str = ""


class ArcadeGameEntry(BaseModel):
    """Single mini-app entry rendered in the Arcade Hub manifest."""

    game_id: str
    title: str
    framework: str
    target_language: str
    output_dir: str
    status: Literal["verified", "repaired", "broken"]
    badge_label: str
    repair_attempts: int = 0
    verdict: GameQAVerdict


class ArcadeHubManifest(BaseModel):
    """Top-level manifest for the generated Language-Learning Arcade Hub."""

    common_css_path: str
    games: list[ArcadeGameEntry] = Field(default_factory=list)
