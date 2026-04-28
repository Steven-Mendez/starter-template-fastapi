## 1. Spec Cleanup (no code change)

- [x] 1.1 Verify the architecture suite already emits the new diagnostic prefix `hexagonal-architecture-conformance:` (it should — landed in the previous turn)
- [x] 1.2 Confirm `tests/architecture/test_skill_checklist_coverage.py` has been deleted (it was; no enforcing meta-test exists for the dropped scenario)
- [x] 1.3 Run `openspec validate decouple-conformance-spec-from-skill` and resolve any reported issues
- [x] 1.4 Run `make test-architecture` and `make lint-arch`; both MUST be green before archive
- [ ] 1.5 Optional: add a `Conformance Diagnostics Reference the Spec Capability` quick check that scans test source files and asserts every architecture test that uses `assert ... <message>` includes a kebab-case capability id followed by `:` in the message (low-priority guard; can be deferred to a follow-up if scope grows)

## 2. Archive

- [x] 2.1 Archive the change with `openspec archive decouple-conformance-spec-from-skill --yes`. The archive step MUST sync deltas into `openspec/specs/hexagonal-architecture-conformance/spec.md` and `openspec/specs/use-case-cohesion/spec.md`
- [x] 2.2 Confirm `openspec list` shows zero active changes after archive
- [x] 2.3 Re-run `make test-architecture` and `make lint-arch` post-archive as a sanity check
