## MODIFIED Requirements

### Requirement: Type checking is strict

`[tool.mypy]` in `pyproject.toml` SHALL set `strict = true`. `make typecheck` SHALL pass with no `# type: ignore` lacking an inline `XXX:` reason comment. Per-module `ignore_missing_imports` overrides are permitted only for genuinely untyped third-party packages and SHALL carry a comment naming the package.

#### Scenario: Strict mode rejects an implicit Any return

- **GIVEN** the codebase with `strict = true` enabled in `pyproject.toml`
- **WHEN** a contributor adds a function whose return type is inferred as `Any` and assigns its result to a `str` variable
- **THEN** `make typecheck` exits non-zero with a clear `[no-any-return]` or `[assignment]` diagnostic

#### Scenario: A `# type: ignore` without a reason fails review

- **GIVEN** a PR adds a bare `# type: ignore[attr-defined]` with no trailing reason comment
- **WHEN** `make typecheck` runs
- **THEN** the gate still passes (mypy accepts the ignore), but the spec marks this as non-compliant and the reviewer rejects the diff

#### Scenario: An unused ignore is flagged

- **GIVEN** a previously needed `# type: ignore[attr-defined]` whose underlying error has been fixed
- **WHEN** `make typecheck` runs under `strict = true`
- **THEN** mypy reports `[unused-ignore]` and the gate fails
