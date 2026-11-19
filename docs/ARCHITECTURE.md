# Architecture — Multi-Framework Arcade Orchestrator

## Overview
`ArcadeLoopOrchestrator` (Google ADK coordinator) orchestrates heterogeneous agent framework workers (**Strands**, **Pydantic AI**, **Microsoft Agent Framework**, **Agno**, **Mastra**) to generate, verify, and repair language-learning arcade mini-apps.

## Core Design Guarantees

1. **Shared Design Tokens First (`common.css`)**
   - Before spawning any worker subprocess, the orchestrator writes `common.css` in the root output directory so every mini-app shares consistent typography, layout, and badge styling.

2. **Per-Worker Isolated Output Directories**
   - Each `WorkerTaskSpec` executes inside its own dedicated directory (`<output_root>/games/<game_id>`), preventing file collisions or cross-worker overwrites.

3. **Subprocess Timeout Enforcement**
   - Worker subprocesses are launched with a strict `timeout_seconds` budget. Hung workers are terminated (`kill()` / `terminate()`) and recorded as failed without stalling the orchestrator loop.

4. **Playwright QA JSON Verdicts**
   - Every generated mini-app is evaluated by a Playwright QA runner returning a structured `GameQAVerdict` (`passed`, `console_errors`, `missing_assets`, `notes`).

5. **Bounded 1-Shot Repair Loop**
   - If QA fails (e.g., missing `game.js` or runtime console errors), the orchestrator invokes at most **1** targeted repair attempt (`max_repair_attempts=1`).
   - If the repair attempt still fails QA, the game is **honestly marked** as broken (`status="broken"`, badge `"Needs Repair / Broken"`) in `ArcadeHubManifest` and the generated `index.html` arcade hub—never masked as passing.
