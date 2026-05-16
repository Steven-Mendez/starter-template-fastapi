# Tasks — remove SpiceDB authorization stub (ROADMAP ETAPA I step 6)

## 1. Pre-flight audit (confirm the no-wiring finding before deleting)

- [ ] 1.1 Re-confirm `build_authorization_container`
      (`src/features/authorization/composition/container.py`) constructs
      only `SQLModelAuthorizationAdapter` and never imports
      `SpiceDBAuthorizationAdapter`.
- [ ] 1.2 Re-confirm a repo-wide grep finds no authorization backend
      selector setting, no `APP_AUTHZ_*` / `APP_SPICEDB_*` env var, and no
      `validate_production` arm referencing SpiceDB (in `AppSettings` and
      any feature `composition/settings.py`).
- [ ] 1.3 Re-confirm `grep -rn -i spicedb src/**/tests/` returns no
      matches and `grep -rn -i spicedb CONTRIBUTING.md pyproject.toml`
      returns no matches.

## 2. Delete the stub package

- [ ] 2.1 Delete `src/features/authorization/adapters/outbound/spicedb/__init__.py`.
- [ ] 2.2 Delete `src/features/authorization/adapters/outbound/spicedb/adapter.py`.
- [ ] 2.3 Delete `src/features/authorization/adapters/outbound/spicedb/README.md`.
- [ ] 2.4 Remove the now-empty `spicedb/` directory.

## 3. Reword code docstrings (wording only — no behavior change)

- [ ] 3.1 `src/features/authorization/__init__.py`: drop ", the SpiceDB
      stub" from the slice-contents sentence.
- [ ] 3.2 `src/features/authorization/adapters/outbound/__init__.py`:
      remove the `spicedb.SpiceDBAuthorizationAdapter` bullet; restate as
      one shipped adapter (`sqlmodel`).
- [ ] 3.3 `src/features/authorization/application/__init__.py`: change
      "(in-repo SQLModel default; SpiceDB stub)" to name only the SQLModel
      adapter.
- [ ] 3.4 `src/features/authorization/application/ports/authorization_port.py`:
      reword the "(in-repo SQLModel default; SpiceDB stub)" line and the
      `check ↔ SpiceDB CheckPermission` mapping list to generic
      Zanzibar/OpenFGA wording. Do NOT change the five method
      names/signatures.
- [ ] 3.5 `src/features/authorization/application/registry.py`: change the
      "Zanzibar parallel" docstring's "a SpiceDB `.zed` schema" to a
      generic "a Zanzibar-style schema `definition`".
- [ ] 3.6 `src/features/authorization/application/hierarchy.py`: change
      "For SpiceDB this would be a schema fragment such as" to a generic
      Zanzibar-style phrasing; keep the example block.
- [ ] 3.7 `src/features/authorization/adapters/outbound/sqlmodel/adapter.py`:
      reword the scaling note "switch to a real ReBAC engine (SpiceDB /
      OpenFGA / AuthZed Cloud)" to "switch to a real ReBAC engine behind
      the `AuthorizationPort`". Do NOT change adapter logic.

## 4. Remove SpiceDB lines from docs (SpiceDB only — no wholesale rewrite)

- [ ] 4.1 `docs/architecture.md` line ~33: drop "the SpiceDB stub" from
      the authorization adapters list.
- [ ] 4.2 `docs/architecture.md` line ~192: remove the `SpiceDB |
      Authorization | …` table row entirely.
- [ ] 4.3 `docs/architecture.md` line ~246: the `S3 and SpiceDB stubs`
      row becomes about the S3 stub only (keep the S3 half — step 7).
- [ ] 4.4 `docs/architecture.md` line ~254: remove "The SpiceDB
      authorization adapter is a stub." sentence; keep the surviving
      "SQLModel adapter is the real one" statement.
- [ ] 4.5 `CLAUDE.md` line ~57: feature-table row → "SQLModel adapter,
      `BootstrapSystemAdmin`" (drop ", SpiceDB stub").
- [ ] 4.6 `CLAUDE.md` line ~141: delete the `adapters/outbound/spicedb/`
      bullet.
- [ ] 4.7 `CLAUDE.md` line ~165: reword the S3 file-storage bullet's
      "(mirrors SpiceDB pattern)" parenthetical to remove the SpiceDB
      reference (do NOT remove the S3 stub itself — step 7).
- [ ] 4.8 `README.md` line ~50: drop ", and the SpiceDB stub" from the
      authorization feature description.
- [ ] 4.9 Confirm no other doc under `docs/` references SpiceDB (grep).

## 5. Spec delta

- [ ] 5.1 `openspec/changes/remove-spicedb-stub/specs/authorization/spec.md`
      authored: REMOVE `SpiceDB adapter is a structural placeholder`;
      MODIFY `AuthorizationPort defines the application-side authorization
      contract`, `Authorization is a self-contained feature slice`, and
      `Authorization config is registered programmatically per feature`
      (full SHALL text restated, scenarios carried forward).

## 6. Verify

- [ ] 6.1 `openspec validate remove-spicedb-stub --strict` passes.
- [ ] 6.2 `make quality` green (lint + arch + typecheck — confirm the
      Import Linter authorization contracts still pass).
- [ ] 6.3 `make test` green.
- [ ] 6.4 Final repo-wide `grep -rn -i spicedb src/ docs/ CLAUDE.md
      README.md CONTRIBUTING.md` returns only intended absences (no
      remaining stub references; archived `openspec/changes/archive/**`
      and memory files are historical and left untouched).
