## 1. Rename the file with history preserved

- [ ] 1.1 Run `git mv src/features/authorization/adapters/outbound/sqlmodel/repository.py src/features/authorization/adapters/outbound/sqlmodel/adapter.py` so `git log --follow` and review tooling recognize the rename.
- [ ] 1.2 Confirm only one file exists at the new path: `ls src/features/authorization/adapters/outbound/sqlmodel/` reports `adapter.py` (plus `__init__.py`, `models.py`), and no `repository.py`.

## 2. Update imports inside the authorization feature

- [ ] 2.1 Update `src/features/authorization/adapters/outbound/sqlmodel/__init__.py:3` to import from `features.authorization.adapters.outbound.sqlmodel.adapter`. This is the only direct importer of the renamed module.
- [ ] 2.2 Verify no other consumer needs an update: `composition/container.py`, `composition/wiring.py`, and every test under `tests/` already import from the `sqlmodel` package (via `__init__.py`), so the rename is transparent to them.

## 3. Verify no other location imports the old path

- [ ] 3.1 Run `rg "authorization\.adapters\.outbound\.sqlmodel\.repository" src/` and confirm zero hits (the only pre-rename hit was `src/features/authorization/adapters/outbound/sqlmodel/__init__.py:3`).
- [ ] 3.2 Run `rg "sqlmodel\.repository" src/features/authorization/` and confirm zero hits (catches both relative and absolute import styles).

## 4. Verify

- [ ] 4.1 `make lint` green.
- [ ] 4.2 `make lint-arch` green (Import Linter contracts unaffected).
- [ ] 4.3 `make typecheck` green.
- [ ] 4.4 `make ci` green (line + branch coverage gates intact).
