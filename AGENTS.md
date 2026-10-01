# Base44 Dev Environment

## Project Overview
Minimal Python project — the entire app is a single `main` file containing `print("hello")`.

## Setup
- `app.py` is a lightweight HTTP server (stdlib only, no dependencies) that runs `main` and serves its output as a styled HTML page on port 3000.
- `docker-compose.base44.yml` uses `python:3.12-slim`, bind-mounts the repo at `/app`, and runs `python3 app.py`.
- No external credentials or secrets needed.

## Verification
- `curl http://localhost:3000/` returns an HTML page displaying "hello".
- Healthcheck probes `http://localhost:3000/` via Python stdlib.
