---
name: project-test-stack
description: pytest commands, markers, and the canonical Docker-skip env var for this repo
metadata:
  type: project
---

Test runner is pytest with three markers declared in `pyproject.toml [tool.pytest.ini_options]`: `unit` (fast, no IO), `integration` (testcontainers / external services), `e2e` (full HTTP flow). `--strict-markers` is on, so a typo'd marker fails collection.

Common commands:

- `make test` — runs `unit` + `e2e` (no Docker).
- `make test-integration` — runs only `integration` (needs Docker).
- `make test-feature FEATURE=<name>` — narrows to one feature dir.
- `make quality` — ruff lint + import-linter contracts + mypy.
- `make ci` — quality + cov + integration (full gate).

Docker-skip env var (canonical, per CLAUDE.md): `KANBAN_SKIP_TESTCONTAINERS=1`. The repo previously had an `AUTH_SKIP_TESTCONTAINERS` alias that was removed in the `strengthen-test-contracts` change — do not reintroduce.

**Why:** the repo's CI gates fan out across these markers and lint/typecheck before integration so a contract drift cannot reach prod silently.

**How to apply:** when writing a new test, pick the marker that matches the actual IO surface — `fakeredis`-backed tests are `unit`, real-Redis testcontainers are `integration`. Mismatched markers were the bug class that motivated `strengthen-test-contracts`.
