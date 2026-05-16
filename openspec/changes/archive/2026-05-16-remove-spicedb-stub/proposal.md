## Why

ROADMAP ETAPA I step 6 ("dejar el repo honesto"): remove the SpiceDB
authorization adapter stub
(`src/features/authorization/adapters/outbound/spicedb/`) and every
code/doc/spec surface that documents it. The ROADMAP decision (line 26)
is explicit: remove non-AWS production-shaped adapters (SMTP, Resend, arq,
SpiceDB); steps 3–5 already deleted SMTP, Resend, and arq. This is the
SpiceDB step.

SpiceDB differs from steps 3–5 in one decisive way and that difference
shapes the whole change:

1. **It is a never-wired structural placeholder, not a selectable
   backend.** Unlike `email_backend` / `jobs_backend`, there is **no**
   authorization backend-selector setting, **no** env var, **no**
   production-validator entry, and **no** `Literal` to narrow.
   `build_authorization_container`
   (`src/features/authorization/composition/container.py`) constructs
   `SQLModelAuthorizationAdapter` unconditionally and the SpiceDB module
   is imported by nothing except its own package `__init__.py`. A
   repo-wide search for an authz backend selector returns nothing.
   Consequently there is **zero production-coherence tension** here — the
   "keep the production validator an honest refusal" decision that
   governed steps 3–5 simply does not apply: there is no validator arm,
   no `Literal` collapse, and no `_VALID_PROD_ENV` axis to repoint. This
   is a pure dead-code deletion plus reference cleanup.

2. **It carries a full package the roadmap is removing.**
   `SpiceDBAuthorizationAdapter` (two modules: `__init__.py`,
   `adapter.py`) plus a 103-line `README.md` documenting a `.zed` schema
   and a SpiceDB-API mapping for an integration the roadmap is dropping.
   None of it executes; the `# pragma: no cover` markers exist precisely
   because the code never runs.

3. **It widens the documented contract with a path nobody can take.**
   Module docstrings (`features/authorization/__init__.py`,
   `adapters/outbound/__init__.py`, `application/__init__.py`,
   `application/ports/authorization_port.py`, `application/registry.py`,
   `application/hierarchy.py`, `adapters/outbound/sqlmodel/adapter.py`),
   the `authorization` capability spec, `docs/architecture.md`,
   `CLAUDE.md`, and `README.md` all describe "the SpiceDB stub" / "swap
   in SpiceDB" as if it were a shipped, swappable adapter. A reader
   cannot tell the SpiceDB path is being retired.

This step deletes the SpiceDB stub only. The `AuthorizationPort`
abstraction — the actual swap boundary — is unchanged and remains the
seam by which a real ReBAC backend could be introduced later. The
SQLModel adapter (the only real `AuthorizationPort` implementation), the
registry, the hierarchy, and every authorization decision are untouched.
Amazon Verified Permissions / AVP is ROADMAP step 53 and is explicitly
out of scope here.

### Key difference from steps 3–5 — no production validator involvement

Steps 3 (SMTP), 4 (Resend), and 5 (arq) each had to weigh "the backend
`Literal` collapses to a dev-only value; keep the production validator
refusing it honestly." That tension does not exist for SpiceDB:

- There is no `authorization_backend` setting, no `APP_AUTHZ_*` env var,
  no `Literal` enumerating authz backends, and no `validate_production`
  arm referencing SpiceDB anywhere in `AppSettings` or any feature's
  `composition/settings.py`. The SpiceDB stub was never selectable.
- The "swap a real backend in later" capability is provided by the
  `AuthorizationPort` Protocol itself, which stays. Removing the dead
  stub does not remove that capability; it removes a non-functional
  illustration of it that names a now-out-of-scope vendor.
- Therefore the only forced changes are: delete the package (incl. its
  README) and reword docstrings/specs/docs that specifically name
  "SpiceDB" to be backend-neutral (the port is still swappable; we just
  stop naming a deleted stub and an out-of-scope vendor). No settings,
  env, validator, migration, or `_VALID_PROD_ENV` change is involved.

The `application/ports/authorization_port.py` docstring currently maps
each port method to a SpiceDB API name (`check ↔ CheckPermission`, etc.)
to teach the Zanzibar API shape. That pedagogical mapping is reworded to
reference the Zanzibar/OpenFGA model generically rather than the deleted
SpiceDB stub — the port shape and its five methods do not change.

## What Changes

- Delete the SpiceDB adapter package
  `src/features/authorization/adapters/outbound/spicedb/`
  (`__init__.py`, `adapter.py`, `README.md`). Nothing imports it outside
  that package, so no call site changes.
- Reword the module docstrings / docstring-embedded references that
  specifically name the deleted SpiceDB stub, keeping each backend-neutral
  (the `AuthorizationPort` is still the documented swap boundary; we stop
  naming a deleted stub):
  - `src/features/authorization/__init__.py` — drop ", the SpiceDB stub"
    from the slice-contents sentence.
  - `src/features/authorization/adapters/outbound/__init__.py` — remove
    the `spicedb.SpiceDBAuthorizationAdapter` bullet; the module now ships
    one adapter (`sqlmodel`).
  - `src/features/authorization/application/__init__.py` — change
    "(in-repo SQLModel default; SpiceDB stub)" to name only the SQLModel
    adapter as the concrete implementation.
  - `src/features/authorization/application/ports/authorization_port.py`
    — keep the five-method Zanzibar-shaped contract; reword the
    "(in-repo SQLModel default; SpiceDB stub)" line and the
    `check ↔ SpiceDB CheckPermission` mapping list to reference the
    Zanzibar/OpenFGA model generically (not the deleted SpiceDB stub).
    The method names and signatures do not change.
  - `src/features/authorization/application/registry.py` — the "Zanzibar
    parallel" docstring's "a SpiceDB `.zed` schema" phrasing becomes a
    generic "a Zanzibar-style schema `definition`" (concept retained,
    vendor stub name dropped).
  - `src/features/authorization/application/hierarchy.py` — "For SpiceDB
    this would be a schema fragment such as" becomes a generic
    Zanzibar-style schema-fragment illustration; the example block is
    kept (it teaches the userset-rewrite concept, not the stub).
  - `src/features/authorization/adapters/outbound/sqlmodel/adapter.py` —
    the scaling note "switch to a real ReBAC engine (SpiceDB / OpenFGA /
    AuthZed Cloud)" is reworded to "switch to a real ReBAC engine behind
    the `AuthorizationPort`" (keeps the swap-is-one-adapter point, drops
    the deleted-stub vendor list). No adapter behavior changes.
- Remove the SpiceDB lines **only** from docs (no wholesale rewrite —
  ROADMAP steps 9/10 own README/CLAUDE re-framing):
  - `docs/architecture.md`: line 33 feature table — drop "the SpiceDB
    stub" from the authorization adapters list; line 192 — remove the
    `SpiceDB | Authorization | Not used today; the adapter is a stub …`
    table row; line 246 — the `S3 and SpiceDB stubs` row becomes about
    the S3 stub only (S3 removal is step 7, out of scope here — keep its
    line, only drop SpiceDB from it); line 254 — remove the "The SpiceDB
    authorization adapter is a stub." sentence, keep the surviving
    statement that the SQLModel adapter is the real one.
  - `CLAUDE.md`: line 57 feature-table row "SQLModel adapter, SpiceDB
    stub, `BootstrapSystemAdmin`" → "SQLModel adapter,
    `BootstrapSystemAdmin`"; line 141 — delete the
    `adapters/outbound/spicedb/ — SpiceDBAuthorizationAdapter stub; one
    swap to drop in a real SpiceDB integration` bullet; line 165 — the
    file-storage S3 bullet "(mirrors SpiceDB pattern)" loses the SpiceDB
    parenthetical (reword to "(stub; raises `NotImplementedError`)"; the
    S3 stub itself is step 7, untouched here).
  - `README.md`: line 50 feature-table row — drop ", and the SpiceDB
    stub" from the authorization description.
- No `CONTRIBUTING.md` change: a line-by-line audit found **zero**
  SpiceDB references (no adapter reference, no example slug — confirmed
  with a case-insensitive grep). This is called out explicitly because
  the step-4 (Resend) audit initially missed `CONTRIBUTING.md`
  references; this time the file genuinely has none.
- No test change: a repo-wide search of `src/**/tests/` for
  `spicedb`/`SpiceDB` returns **no matches**. There is no SpiceDB unit
  test, contract test, or port-parity test to delete. (The
  `AuthorizationPort` contract suite, if any, exercises the SQLModel
  adapter, not the stub — confirmed: nothing under `tests/` names the
  stub.)
- No `pyproject.toml` change: no SpiceDB dependency, optional-dependency
  extra, or Import Linter entry exists (the stub used only stdlib +
  in-repo imports). Confirmed with grep.
- No `.env.example` change: the stub had no env surface.
- The `ROADMAP.md` step-6 checkbox is flipped to `[x]` by the archive
  step, not by this change.

**Production-validator coherence (constraint check):** N/A — there is no
authorization backend selector, no env var, and no `validate_production`
arm that references SpiceDB anywhere in the codebase (verified). Unlike
ROADMAP steps 3–5, this removal forces no validator wording change, no
`Literal` narrowing, and no `_VALID_PROD_ENV` repoint. This is the
explicit, audited finding the parent asked to confirm.

**Capabilities — Modified**
- `authorization`:
  - `SpiceDB adapter is a structural placeholder` is **removed entirely**
    (REMOVED) — the requirement is wholly about the deleted stub.
  - `AuthorizationPort defines the application-side authorization
    contract` is restated so its "Two adapters implement the port"
    scenario becomes a single-adapter scenario asserting only the
    SQLModel adapter implements the port (the five-method port contract
    is unchanged).
  - `Authorization is a self-contained feature slice` is restated so the
    slice-contents sentence no longer enumerates "the SpiceDB stub" (the
    slice still contains the port, registry, SQLModel adapter, and
    `BootstrapSystemAdmin`; the self-containment guarantee is unchanged).
  - `Authorization config is registered programmatically per feature` is
    restated so "the single source of truth read by the SQLModel adapter
    and any future adapter (SpiceDB, OpenFGA)" no longer names the
    deleted SpiceDB stub — it reads "the SQLModel adapter and any future
    `AuthorizationPort` adapter" (the registry behavior is unchanged).

**Capabilities — New**
- None.

## Impact

- **Deleted package**: `src/features/authorization/adapters/outbound/spicedb/`
  — all three files: `__init__.py`, `adapter.py`, and `README.md` (the
  103-line `.zed`-schema / API-mapping document).
- **Code (docstring/wording only — no behavior change)**:
  - `src/features/authorization/__init__.py` (drop SpiceDB-stub clause)
  - `src/features/authorization/adapters/outbound/__init__.py` (remove
    the SpiceDB-adapter bullet; one adapter now ships)
  - `src/features/authorization/application/__init__.py` (drop the
    "SpiceDB stub" parenthetical)
  - `src/features/authorization/application/ports/authorization_port.py`
    (reword the implementations parenthetical and the SpiceDB-API mapping
    list to generic Zanzibar/OpenFGA wording; port methods unchanged)
  - `src/features/authorization/application/registry.py` (generic
    Zanzibar-schema phrasing)
  - `src/features/authorization/application/hierarchy.py` (generic
    Zanzibar schema-fragment phrasing; example block retained)
  - `src/features/authorization/adapters/outbound/sqlmodel/adapter.py`
    (scaling-note vendor list → "a real ReBAC engine behind the
    `AuthorizationPort`"; adapter logic untouched)
- **Migrations**: none. SpiceDB was a non-functional in-memory stub with
  zero database footprint — no table, column, index, or persisted state
  is touched. (`AppSettings.model_config` is irrelevant here — the stub
  had no settings surface at all.)
- **Settings / env / production validator**: none. There is no
  authorization backend selector, no `APP_AUTHZ_*`/`APP_SPICEDB_*` env
  var, no `Literal` to narrow, and no `validate_production` arm naming
  SpiceDB anywhere (`AppSettings`,
  `src/features/authorization/composition/settings.py` if present, and a
  repo-wide grep all confirm). This is the load-bearing distinction from
  ROADMAP steps 3–5.
- **Tests**: none deleted or edited. `src/**/tests/` contains no
  `spicedb`/`SpiceDB` reference (verified). The Import Linter "each port
  has at least one working adapter under test" guarantee is satisfied by
  the surviving SQLModel adapter; removing a never-tested stub does not
  weaken it.
- **Dependencies / `pyproject.toml`**: none. The stub imported only
  `uuid`, `__future__`, and two in-repo authorization modules. No
  dependency, optional-dependency extra, or Import Linter
  `forbidden_modules` entry references SpiceDB.
- **Docs (SpiceDB lines only — no wholesale rewrite; steps 9/10 own
  README/CLAUDE re-framing, step 7 owns S3-stub removal)**:
  `docs/architecture.md`, `CLAUDE.md`, `README.md`. `CONTRIBUTING.md`
  audited line-by-line and **has no SpiceDB reference** — no edit.
- **Production behavior**: unchanged. The SpiceDB stub never ran in any
  environment (it was constructed by nothing and raised
  `NotImplementedError` if it ever had been). No deployment can be
  affected; there is no env var an operator could have set. Any
  hypothetical project that had hand-wired `SpiceDBAuthorizationAdapter`
  was already non-functional by construction (every method raised).
- **Quality gate**: `make quality` and `make test` MUST stay green after
  the removal. The Import Linter authorization-layering contracts and the
  "Authorization does not import from auth" contract are unaffected
  (the deleted package imported only in-repo authorization modules and
  stdlib). `make typecheck` is unaffected (nothing imported the deleted
  symbols outside the deleted package).

## Out of scope (do NOT touch)

- The SQLModel `AuthorizationPort` adapter
  (`src/features/authorization/adapters/outbound/sqlmodel/`) — it is the
  only real implementation and stays exactly as-is. Only its docstring's
  SpiceDB-naming scaling note is reworded; no logic, query, or signature
  changes.
- The `AuthorizationRegistry`, the relation hierarchy, the parent-walk
  resolver, `BootstrapSystemAdmin`, and every authorization decision —
  unchanged. This change removes dead illustration code, not behavior.
- Amazon Verified Permissions / AVP / AWS Cedar or any AWS authorization
  integration — ROADMAP step 53. Do not add an AVP backend value, an
  authz backend selector, or any AWS authz code/config here.
- The S3 file-storage stub (`src/features/file_storage/adapters/outbound/s3/`)
  — ROADMAP step 7. Where a doc line bundles "S3 and SpiceDB stubs",
  only the SpiceDB half is removed; the S3 line is left for step 7.
- Any broader rewrite of `README.md` or `CLAUDE.md` beyond deleting
  SpiceDB lines / restating the authorization row honestly — ROADMAP
  steps 9/10.
- The `docs/operations.md` "production refuses to start if…" narrative —
  ROADMAP step 11. (SpiceDB has no entry there to begin with; nothing to
  do, called out for completeness.)

This change is strictly ROADMAP ETAPA I step 6. It does not advance step
7 (S3 stub), steps 8–12 (api.md, README/CLAUDE/operations rewrites, cli
docs), or any ETAPA II+ work, and it adds no AWS code.
