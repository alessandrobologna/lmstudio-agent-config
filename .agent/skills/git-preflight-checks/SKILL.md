---
name: git-preflight-checks
description: Run CI-style preflight QA checks and guide the user through a clean commit/push workflow by mirroring `.github/workflows/ci.yml`. Use when asked to verify repo readiness, run pre-commit/pre-push checks, ensure CI passes locally, or before committing/pushing changes.
---

# Git Preflight Checks

## Overview
Run the same checks as CI before committing or pushing. Always derive commands from `.github/workflows/ci.yml`, execute them in order, and guide the user through fixing failures before proceeding.

## Workflow
1. Inspect repo state
- Run `git status -sb`.
- If there are uncommitted changes, call them out. This is expected if formatting fixes were applied; confirm whether to continue.

2. Read CI workflow
- Open `.github/workflows/ci.yml`.
- Extract `run:` commands in the order they appear for the primary CI job.
- Do not invent commands. The workflow is the source of truth.

3. Prepare environment
- Ensure required tools referenced by `run:` commands are available (for example `uv`, `python`).
- If the workflow pins a Python version via `actions/setup-python`, check `python --version` and warn if it differs.
- Ignore `uses:` steps other than tool setup; focus on reproducing `run:` commands locally.

4. Execute checks
- Run each `run:` command exactly as written in CI, in the same order.
- Stop on the first failure and report the error.
- If a failure is fixable by formatting (for example `ruff format --check`), ask whether to apply the formatter and re-run the checks.

5. Final readiness
- Run `git status -sb` again and summarize any changes.
- Confirm all checks passed and ask whether to proceed with commit/push.

## Notes
- If `.github/workflows/ci.yml` is missing or doesn’t contain `run:` steps, stop and ask the user how they want to proceed.
- Keep the process interactive: always ask before making changes (like formatting or auto-fixes).
