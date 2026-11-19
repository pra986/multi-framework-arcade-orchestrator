from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Callable

from .models import ArcadeGameEntry, ArcadeHubManifest, GameQAVerdict, WorkerTaskSpec

DEFAULT_COMMON_CSS = """:root {
  --bg: #0f172a;
  --fg: #f8fafc;
  --accent: #38bdf8;
  --ok: #22c55e;
  --warn: #f59e0b;
  --err: #ef4444;
}
body {
  margin: 0;
  font-family: system-ui, -apple-system, sans-serif;
  background: var(--bg);
  color: var(--fg);
}
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}
.badge-verified { background: var(--ok); color: #052e16; }
.badge-repaired { background: var(--warn); color: #451a03; }
.badge-broken { background: var(--err); color: #450a0a; }
"""

QARunner = Callable[[str, Path], GameQAVerdict]
RepairRunner = Callable[[WorkerTaskSpec, Path, GameQAVerdict], bool]


def default_playwright_qa(game_id: str, worker_dir: Path) -> GameQAVerdict:
    """Validate required game artifacts and optionally run Playwright console checks."""
    index_path = worker_dir / "index.html"
    game_js_path = worker_dir / "game.js"
    has_index = index_path.is_file()
    has_game_js = game_js_path.is_file()

    missing_assets: list[str] = []
    if not has_index:
        missing_assets.append("index.html")
    if not has_game_js:
        missing_assets.append("game.js")

    console_errors: list[str] = []
    notes = ""

    if has_index and has_game_js:
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.on(
                    "pageerror",
                    lambda exc: console_errors.append(str(exc)),
                )
                page.on(
                    "console",
                    lambda msg: console_errors.append(msg.text)
                    if msg.type == "error"
                    else None,
                )
                page.goto(index_path.resolve().as_uri(), wait_until="load", timeout=5000)
                browser.close()
        except ImportError:
            notes = "Playwright not installed; verified static artifacts only."
        except Exception as exc:
            console_errors.append(str(exc))

    passed = has_index and has_game_js and len(console_errors) == 0
    verdict = GameQAVerdict(
        game_id=game_id,
        passed=passed,
        has_index_html=has_index,
        has_game_js=has_game_js,
        console_errors=console_errors,
        missing_assets=missing_assets,
        notes=notes,
    )
    (worker_dir / "qa_verdict.json").write_text(
        verdict.model_dump_json(indent=2), encoding="utf-8"
    )
    return verdict


class ArcadeLoopOrchestrator:
    """Coordinates isolated multi-framework game workers, QA, and bounded repair."""

    def __init__(
        self,
        output_dir: Path | str,
        qa_runner: QARunner | None = None,
        repair_runner: RepairRunner | None = None,
        max_repair_attempts: int = 1,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.games_dir = self.output_dir / "games"
        self.qa_runner = qa_runner or default_playwright_qa
        self.repair_runner = repair_runner
        self.max_repair_attempts = max(0, min(1, max_repair_attempts))

    def author_common_css(self) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        css_path = self.output_dir / "common.css"
        css_path.write_text(DEFAULT_COMMON_CSS, encoding="utf-8")
        return css_path

    def worker_output_dir(self, game_id: str) -> Path:
        target = (self.games_dir / game_id).resolve()
        root = self.games_dir.resolve()
        if root not in target.parents:
            raise ValueError(f"Unsafe game_id outside games directory: {game_id}")
        target.mkdir(parents=True, exist_ok=True)
        return target

    def run_worker(self, task: WorkerTaskSpec, worker_dir: Path) -> tuple[bool, str]:
        if not task.worker_cmd:
            return False, "No worker command specified."

        env = os.environ.copy()
        env["ARCADE_GAME_ID"] = task.game_id
        env["ARCADE_OUTPUT_DIR"] = str(worker_dir)
        env["ARCADE_COMMON_CSS"] = str(self.output_dir / "common.css")

        proc = subprocess.Popen(
            task.worker_cmd,
            cwd=str(worker_dir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            _, stderr = proc.communicate(timeout=task.timeout_seconds)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return True, f"Worker timed out after {task.timeout_seconds}s and was killed."

        if proc.returncode != 0:
            return False, f"Worker exited with code {proc.returncode}: {stderr.strip()}"
        return False, ""

    def _attempt_repair(
        self,
        task: WorkerTaskSpec,
        worker_dir: Path,
        verdict: GameQAVerdict,
    ) -> bool:
        if self.repair_runner is not None:
            return bool(self.repair_runner(task, worker_dir, verdict))
        return False

    def _build_hub_html(self, manifest: ArcadeHubManifest) -> str:
        cards = []
        for game in manifest.games:
            badge_cls = f"badge-{game.status}"
            cards.append(
                f"<article class='card'>"
                f"<h2>{game.title}</h2>"
                f"<span class='badge {badge_cls}'>{game.badge_label}</span>"
                f"<p>Framework: {game.framework} | Language: {game.target_language}</p>"
                f"<a href='games/{game.game_id}/index.html'>Play</a>"
                f"</article>"
            )
        joined = "\n".join(cards)
        return (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>Arcade Hub</title>"
            "<link rel='stylesheet' href='common.css'></head>"
            f"<body><h1>Multi-Framework Arcade Hub</h1>{joined}</body></html>"
        )

    def run_all(self, tasks: list[WorkerTaskSpec]) -> ArcadeHubManifest:
        css_path = self.author_common_css()
        entries: list[ArcadeGameEntry] = []

        for task in tasks:
            worker_dir = self.worker_output_dir(task.game_id)
            timed_out, worker_note = self.run_worker(task, worker_dir)

            if timed_out:
                verdict = GameQAVerdict(
                    game_id=task.game_id,
                    passed=False,
                    has_index_html=(worker_dir / "index.html").is_file(),
                    has_game_js=(worker_dir / "game.js").is_file(),
                    console_errors=[],
                    missing_assets=[],
                    notes=worker_note,
                )
                (worker_dir / "qa_verdict.json").write_text(
                    verdict.model_dump_json(indent=2), encoding="utf-8"
                )
                entries.append(
                    ArcadeGameEntry(
                        game_id=task.game_id,
                        title=task.title,
                        framework=task.framework,
                        target_language=task.target_language,
                        output_dir=str(worker_dir),
                        status="broken",
                        badge_label="Broken (Timed Out)",
                        repair_attempts=0,
                        verdict=verdict,
                    )
                )
                continue

            verdict = self.qa_runner(task.game_id, worker_dir)
            if worker_note and not verdict.notes:
                verdict = verdict.model_copy(update={"notes": worker_note})

            repair_attempts = 0
            if not verdict.passed and self.max_repair_attempts > 0:
                repair_attempts = 1
                self._attempt_repair(task, worker_dir, verdict)
                verdict = self.qa_runner(task.game_id, worker_dir)

            if verdict.passed and repair_attempts == 0:
                status = "verified"
                badge_label = "Verified"
            elif verdict.passed and repair_attempts > 0:
                status = "repaired"
                badge_label = "Repaired"
            else:
                status = "broken"
                badge_label = "Broken"

            entries.append(
                ArcadeGameEntry(
                    game_id=task.game_id,
                    title=task.title,
                    framework=task.framework,
                    target_language=task.target_language,
                    output_dir=str(worker_dir),
                    status=status,
                    badge_label=badge_label,
                    repair_attempts=repair_attempts,
                    verdict=verdict,
                )
            )

        manifest = ArcadeHubManifest(common_css_path=str(css_path), games=entries)
        (self.output_dir / "hub.json").write_text(
            manifest.model_dump_json(indent=2), encoding="utf-8"
        )
        (self.output_dir / "index.html").write_text(
            self._build_hub_html(manifest), encoding="utf-8"
        )
        return manifest
