---
name: pytest-first
description: Add or improve pytest tests and ensure DoD passes. Use when adding endpoints, refactoring logic, or verifying.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---
Rules:
- New endpoint => test.
- Pure logic => unit tests.
- No network calls in tests.
- Run: docker compose run --rm web pytest
