from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .engine import ArcadeLoopOrchestrator
from .models import WorkerTaskSpec

DEMO_WORKER_SCRIPT = (
    "import os, pathlib; "
    "out = pathlib.Path(os.environ['ARCADE_OUTPUT_DIR']); "
    "out.joinpath('index.html').write_text('<!doctype html><html><body><script src=\"game.js\"></script></body></html>', encoding='utf-8'); "
    "out.joinpath('game.js').write_text('console.log(\"arcade ready\");', encoding='utf-8')"
)


def build_demo_tasks() -> list[WorkerTaskSpec]:
    return [
        WorkerTaskSpec(
            game_id="neon-snake",
            title="Neon Snake",
            framework="strands",
            target_language="JavaScript",
            prompt="Build a retro neon snake arcade game.",
            timeout_seconds=15.0,
            worker_cmd=[sys.executable, "-c", DEMO_WORKER_SCRIPT],
        ),
        WorkerTaskSpec(
            game_id="orbital-pong",
            title="Orbital Pong",
            framework="pydantic-ai",
            target_language="JavaScript",
            prompt="Build an orbital pong arcade game.",
            timeout_seconds=15.0,
            worker_cmd=[sys.executable, "-c", DEMO_WORKER_SCRIPT],
        ),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the multi-framework arcade loop orchestrator demo."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./arcade_dist"),
        help="Directory where common.css, games/, hub.json, and index.html are written.",
    )
    args = parser.parse_args(argv)

    orchestrator = ArcadeLoopOrchestrator(output_dir=args.output_dir)
    manifest = orchestrator.run_all(build_demo_tasks())
    print(manifest.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
