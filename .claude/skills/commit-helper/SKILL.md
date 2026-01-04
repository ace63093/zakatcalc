---
name: commit-helper
description: Create clean incremental commits and summaries. Use when asked to commit/checkpoint or after milestones.
allowed-tools: Bash, Git, Read, Grep
---
Workflow:
- git status; git diff
- split large changes
- short message <=72 chars + optional why
- print commit hash + summary
