---
name: docker-dev-loop
description: Run, debug, and validate the local Docker dev loop (docker compose up, logs, ports). Use when compose/runtime/port issues happen.
allowed-tools: Bash, Read, Grep, Glob
---
Checklist:
- docker compose config
- docker compose up --build
- docker compose logs -n 200
- curl health/pricing
- Apply minimal fixes.
