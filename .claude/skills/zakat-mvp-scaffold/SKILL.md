---
name: zakat-mvp-scaffold
description: Build or regenerate the Zakat app MVP scaffold (Flask app factory, templates, Dockerfile, docker-compose, gunicorn, pytest, README). Use when asked to start from scratch, scaffold, bootstrap, or set up the project structure.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Git
---
When active:
- Propose structure first, then implement.
- Defaults: Python 3.12, Flask app factory, templates+minimal JS, /, /healthz, /api/v1/pricing, port 8080, gunicorn, pytest, README.
- One scaffold commit: "Scaffold MVP (Flask + Docker + tests)".
