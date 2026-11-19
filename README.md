# Multi-Framework Arcade Orchestrator

**Project 24 / A7R: Agentic Track — Agent Loop Language-Learning Arcade**

A production-minded **Google ADK** orchestrator that coordinates **Strands**, **Pydantic AI**, **Microsoft Agent Framework (MAF)**, **Agno**, and **Mastra** workers inside isolated workspace folders to build, verify, and repair interactive language-learning arcade mini-apps using **Playwright QA** and a **bounded 1-shot repair loop**.

---

## Architecture

```
+-------------------------------------------------------------------+
|                     Google ADK Orchestrator                       |
|  - Stage scheduler, data-contract validator, repair budget guard  |
+----+-----------+------------+------------+-----------+------------+
     |           |            |            |           |
     v           v            v            v           v
+---------+ +----------+ +--------+  +--------+  +---------+
| Strands | |PydanticAI| |  MAF   |  |  Agno  |  | Mastra  |
| worker/ | | worker/  | |worker/ |  |worker/ |  | worker/ |
+----+----+ +----+-----+ +---+----+  +---+----+  +----+----+
     |           |           |           |            |
     +-----------+-----------+-----+-----+------------+
                                   |
                                   v
                   +-------------------------------+
                   |    Playwright QA Runner       |
                   |  - Headless DOM & quiz checks |
                   |  - Bounded 1-shot repair hook |
                   +-------------------------------+
```

Each framework worker operates strictly within its own isolated folder (`workers/strands/`, `workers/pydantic_ai/`, `workers/maf/`, `workers/agno/`, `workers/mastra/`), preventing cross-framework dependency conflicts and ensuring reproducible artifact outputs.

---

## 6-Stage Workflow

1. **Stage 1 — Prompt & Arcade Spec Synthesis (Google ADK)**: Parses the target language, proficiency level, and arcade game mode into a typed `ArcadeTaskSpec`.
2. **Stage 2 — Isolated Workspace Provisioning**: Initializes per-framework isolated folders and enforces clean-room path boundaries.
3. **Stage 3 — Parallel / Sequential Worker Execution**: Dispatches tasks to Strands, Pydantic AI, MAF, Agno, and Mastra workers to generate language-learning arcade modules.
4. **Stage 4 — Typed Data Contract Validation**: Validates every worker output against the shared `WorkerArtifact` schema before QA.
5. **Stage 5 — Playwright QA Verification**: Launches headless Chromium via Playwright to verify page load, interactive vocabulary/grammar controls, scoring state, and zero console/runtime errors.
6. **Stage 6 — Bounded 1-Shot Repair**: If Playwright QA reports a failure, the orchestrator feeds the structured failure trace back to the responsible worker for **at most 1 repair attempt**, then re-verifies and emits the final `OrchestrationReport`.

---

## Data Contract

All orchestrator-worker-QA handoffs use a strict typed JSON/Pydantic contract:

- **`ArcadeTaskSpec`**: `task_id`, `target_language`, `level`, `game_mode`, `frameworks`, `max_repairs` (default `1`).
- **`WorkerArtifact`**: `framework`, `workspace_dir`, `entry_file`, `status` (`generated` | `repaired` | `failed`), `metadata`.
- **`PlaywrightQAResult`**: `framework`, `passed`, `checks_run`, `console_errors`, `failure_summary`.
- **`OrchestrationReport`**: `task_id`, `artifacts`, `qa_results`, `repairs_attempted`, `overall_passed`.

---

## Production Controls

- **Folder Isolation**: Workers cannot read or mutate sibling framework directories.
- **Bounded 1-Shot Repair**: `max_repairs = 1` hard cap prevents infinite self-healing loops and runaway token spend.
- **Playwright QA Gate**: No worker artifact is marked passing without headless browser verification.
- **Fail-Fast Contract Checks**: Schema mismatches halt the pipeline before browser execution.
- **Deterministic Run Manifests**: Every run records status, repair count, and QA diagnostics.

---

## Local Setup

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt
pip install -e ".[dev]"

# 3. Install Playwright browsers
playwright install chromium

# 4. Configure environment variables
cp .env.example .env

# 5. Run tests
pytest
```

---

## Attribution

Inspired by and adapted from the pinned reference implementation in [`ed-donner/agents`](https://github.com/ed-donner/agents) (`5_agent_frameworks/5_agent_loop`).

## License

MIT License — see [LICENSE](LICENSE) for details.
