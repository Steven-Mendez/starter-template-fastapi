## Why

After `refactor-to-feature-first` and `testing-suite-foundation` land, the repository carries a strong opinion on how to build and test a feature, but that opinion lives only in the Kanban example and a long architecture guide. Anyone cloning the template needs a fast, copy-pasteable starting point for a new feature plus updated guidance that matches the new layout. Without this change, the conventions are implicit, the existing `hex-design-guide.md` still describes the old `src/{api,application,domain,infrastructure}` layout, and the root `README.md` references paths that no longer exist.

## What Changes

- Add `src/features/_template/` containing an empty but compilable feature scaffold mirroring Kanban's structure (placeholder modules, port Protocols, composition stub, tests stub) plus a thorough `README.md` walking the developer through "create a new feature in 10 minutes": copy the folder, rename, define the domain aggregate, declare ports, write a use case, plug an adapter, register in `src/main.py`, write tests.
- Rewrite `hex-design-guide.md` to reference the feature-first layout, document the inbound port Protocol convention, explain platform vs feature boundaries, document the import-linter contracts, and link to Kanban as the canonical example.
- Rewrite the root `README.md` "Quick start", "Project layout", "Conformance", and "OpenSpec" sections so paths and commands match the new layout. Add an "Add a new feature" section linking to `_template/README.md`.
- Add a CONTRIBUTING-style note pointing to the OpenSpec workflow and the SDD/openspec skills.

## Capabilities

### New Capabilities
- `feature-template`: The `src/features/_template/` scaffold and the documented "how to add a feature" workflow that future developers will use.
- `architecture-docs`: The updated architecture documentation (`hex-design-guide.md`, root `README.md` architecture sections) describing the feature-first layout, platform boundary, port conventions, and conformance contracts.

### Modified Capabilities
<!-- None: prior changes register the canonical specs; this change introduces docs/template capabilities for the first time. -->

## Impact

- **Filesystem**: New tree under `src/features/_template/` (compilable but inert; no routes registered). New / rewritten markdown files (`hex-design-guide.md`, root `README.md`).
- **Configuration**: `_template/` is excluded from runtime registration in `src/main.py` (no `register__template`); import-linter contracts MAY explicitly allow `_template` as a dormant feature (or simply not register it).
- **Behavior**: No runtime behavior change.
- **Sequencing**: Depends on both `refactor-to-feature-first` (provides the layout to mirror) and `testing-suite-foundation` (provides the test conventions documented in `_template/README.md`).
