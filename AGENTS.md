# NEXORA AI Builder — Base44 dev environment

## What this is
NEXORA AI Builder is a full-stack, IDE-style AI software-development workspace
(Prompt → Enhance → Understand → Plan → Build → Inspect → Files → Preview → Test →
Fix → Verify).

This repository is an **imported repo running in a Docker sandbox**. It is NOT a
Base44-builder app: there is no Base44 SDK, no Base44 entities, and no
`window.base44_sdk`. Persistence is a real SQLite database, and secrets are
delivered through the platform-managed env file.

## Stack
- **Backend**: FastAPI + uvicorn (live reload), SQLite via the stdlib `sqlite3`
  (no ORM). Code lives in `backend/`.
- **Frontend**: dependency-free ES-module SPA served by FastAPI from `frontend/`
  (single origin — no separate dev server, no build step).
- **Compose**: `docker-compose.base44.yml` runs `python:3.12-slim` with the repo
  bind-mounted at `/app`; dependencies install at container start.

## Running
```bash
docker compose -f docker-compose.base44.yml up -d --build
```
Entry point: <http://localhost:3000> (also the preview port). Health: `/api/health`.
Preview processes for generated projects use published ports **4100–4103**.

## Key layout
- `backend/db.py`, `backend/repository.py` — schema + all entity persistence.
- `backend/ai/providers.py` — provider layer (Anthropic, OpenAI,
  OpenAI-compatible, OpenRouter, Ollama). **Keys are read from the environment
  only** and are never written to the database.
- `backend/ai/service.py` — AI service (chat, enhance, plan, generate-files).
- `backend/agents/` — `ToolRegistry`/`ToolExecutor` (13 real tools), specialist
  `roles.py`, and `runtime.py` (the shared workflow orchestrator).
- `backend/services/` — `filesystem.py` (DB-backed FilesystemAdapter),
  `execution.py` (real subprocess execution), `preview.py` (real process
  management), `diff.py`, `verification.py`, `memory.py`, `templates.py`.
- `frontend/js/` — `app.js` (shell, region rendering, splitters, shortcuts),
  `actions.js` (all state changes), `components.js`, `workspace.js`,
  `settings.js`, `editor.js`.

## Things that are non-obvious
- **Rendering**: the app re-renders by region, keyed on a state signature.
  Text inputs are preserved via `data-field` attributes + `rebuildPreservingFocus`.
  When adding an input that triggers a re-render, give it a `dataset.field`.
- **Editor**: `mountEditor` is synchronous — it shows a real plain-text editor
  immediately and upgrades in place to Monaco only if the CDN responds. Monaco is
  never required for the editor to work.
- **AI is optional**. With no provider key the app still boots and runs: it
  returns HTTP 503 for enhance, and the agent's build stage reports
  `blocked` ("requires a configured AI provider"). This degradation is
  intentional — do not replace it with fake responses.
- **Execution is real**. The terminal runs genuine commands via `subprocess` in a
  materialized workspace. Runtimes missing from the image (node/npm/git/pytest in
  `python:3.12-slim`) are reported as absent rather than simulated. Building a
  React project therefore reports "external execution backend required".
- **Preview is real**. `PreviewAdapter` starts an actual process and returns a
  real published-port URL; if no runnable entry point exists it says so.
- **Verification is evidence-based**: claims are re-checked against the file store
  or real exit codes. The AI asserting success never marks a task verified.

## Verifying it works
```bash
curl -s localhost:3000/api/health            # {"status":"ok",...}
curl -s localhost:3000/api/system            # capabilities, providers, tools
curl -s -X POST localhost:3000/api/projects -H 'Content-Type: application/json' \
  -d '{"name":"Demo","template":"react_vite_ts"}'
```

## Secrets
Optional AI provider credentials (see `.base44/environment.json`) are delivered to
`/run/base44/app.env` and wired into compose as the last `env_file`. The app boots
without them. Never hardcode a key.
