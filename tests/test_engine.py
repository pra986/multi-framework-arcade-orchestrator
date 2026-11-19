from __future__ import annotations

import sys
from pathlib import Path

from arcade_orchestrator.engine import ArcadeLoopOrchestrator
from arcade_orchestrator.models import GameQAVerdict, WorkerTaskSpec


def test_hung_worker_timeout_termination(tmp_path: Path) -> None:
    orchestrator = ArcadeLoopOrchestrator(output_dir=tmp_path)
    task = WorkerTaskSpec(
        game_id="hung-game",
        title="Hung Game",
        framework="strands",
        target_language="JavaScript",
        prompt="Hang forever",
        timeout_seconds=0.3,
        worker_cmd=[sys.executable, "-c", "import time; time.sleep(10)"],
    )

    manifest = orchestrator.run_all([task])
    entry = manifest.games[0]

    assert entry.status == "broken"
    assert "Timed Out" in entry.badge_label
    assert entry.repair_attempts == 0
    assert entry.verdict.passed is False
    assert "timed out" in entry.verdict.notes.lower()


def test_missing_game_js_triggers_single_repair(tmp_path: Path) -> None:
    repair_calls = 0

    def repair_missing_js(
        task: WorkerTaskSpec, worker_dir: Path, verdict: GameQAVerdict
    ) -> bool:
        nonlocal repair_calls
        repair_calls += 1
        assert "game.js" in verdict.missing_assets
        (worker_dir / "game.js").write_text("console.log('repaired');", encoding="utf-8")
        return True

    orchestrator = ArcadeLoopOrchestrator(
        output_dir=tmp_path,
        repair_runner=repair_missing_js,
        max_repair_attempts=1,
    )
    script = (
        "import os, pathlib; "
        "out = pathlib.Path(os.environ['ARCADE_OUTPUT_DIR']); "
        "out.joinpath('index.html').write_text('<html></html>', encoding='utf-8')"
    )
    task = WorkerTaskSpec(
        game_id="missing-js",
        title="Missing JS Game",
        framework="pydantic-ai",
        target_language="JavaScript",
        prompt="Write index.html only",
        timeout_seconds=5.0,
        worker_cmd=[sys.executable, "-c", script],
    )

    manifest = orchestrator.run_all([task])
    entry = manifest.games[0]

    assert repair_calls == 1
    assert entry.repair_attempts == 1
    assert entry.status == "repaired"
    assert entry.badge_label == "Repaired"
    assert entry.verdict.passed is True


def test_honest_broken_marking_after_failed_repair(tmp_path: Path) -> None:
    repair_calls = 0

    def failing_repair(
        task: WorkerTaskSpec, worker_dir: Path, verdict: GameQAVerdict
    ) -> bool:
        nonlocal repair_calls
        repair_calls += 1
        return False

    orchestrator = ArcadeLoopOrchestrator(
        output_dir=tmp_path,
        repair_runner=failing_repair,
        max_repair_attempts=1,
    )
    task = WorkerTaskSpec(
        game_id="broken-game",
        title="Broken Game",
        framework="agno",
        target_language="JavaScript",
        prompt="Produce nothing",
        timeout_seconds=5.0,
        worker_cmd=[sys.executable, "-c", "pass"],
    )

    manifest = orchestrator.run_all([task])
    entry = manifest.games[0]

    assert repair_calls == 1
    assert entry.repair_attempts == 1
    assert entry.status == "broken"
    assert entry.badge_label == "Broken"
    assert entry.verdict.passed is False
    hub_html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "badge-broken" in hub_html


def test_per_worker_directory_isolation(tmp_path: Path) -> None:
    orchestrator = ArcadeLoopOrchestrator(output_dir=tmp_path)
    script = (
        "import os, pathlib; "
        "out = pathlib.Path(os.environ['ARCADE_OUTPUT_DIR']); "
        "gid = os.environ['ARCADE_GAME_ID']; "
        "out.joinpath('index.html').write_text(f'<h1>{gid}</h1>', encoding='utf-8'); "
        "out.joinpath('game.js').write_text(f'console.log({gid!r});', encoding='utf-8')"
    )
    tasks = [
        WorkerTaskSpec(
            game_id="game-alpha",
            title="Game Alpha",
            framework="maf",
            target_language="JavaScript",
            prompt="Alpha",
            timeout_seconds=5.0,
            worker_cmd=[sys.executable, "-c", script],
        ),
        WorkerTaskSpec(
            game_id="game-beta",
            title="Game Beta",
            framework="mastra",
            target_language="TypeScript",
            prompt="Beta",
            timeout_seconds=5.0,
            worker_cmd=[sys.executable, "-c", script],
        ),
    ]

    manifest = orchestrator.run_all(tasks)
    assert (tmp_path / "common.css").is_file()
    assert len(manifest.games) == 2

    dir_a = tmp_path / "games" / "game-alpha"
    dir_b = tmp_path / "games" / "game-beta"
    assert dir_a != dir_b
    assert "game-alpha" in (dir_a / "index.html").read_text(encoding="utf-8")
    assert "game-beta" in (dir_b / "index.html").read_text(encoding="utf-8")
    assert "game-beta" not in (dir_a / "index.html").read_text(encoding="utf-8")
