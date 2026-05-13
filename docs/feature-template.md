# Feature Template Guide

The in-tree `_template` feature was removed (see the OpenSpec change
`remove-template-feature`). The scaffold now lives only in git history.

## Where to find the scaffold

The last commit before deletion contains the full directory under
`src/features/_template/`. Recover it with:

```bash
git log --diff-filter=D --summary -- src/features/_template | head -20
# find the SHA where _template was deleted, then:
git show <sha>^:src/features/_template > /tmp/_template-tree.txt
# or check out the directory at that revision:
git checkout <sha>^ -- src/features/_template
```

## Adding a new feature

Once you have the scaffold copied into `src/features/<feature_name>/`,
follow the steps under "Adding a new feature" in `CLAUDE.md`. The short
version:

1. Rename the entity, table, routes, and tests inside the copy.
2. Register your resource types with the authorization registry from your
   feature's wiring module.
3. Build your feature's container in `src/main.py` after the authorization
   container exists.
4. Gate HTTP routes with `require_authorization(...)`.
5. If you need atomic authorization writes, take a
   `user_authz_version_factory` parameter on the container.
6. If the feature sends email or does deferred work, register templates and
   handlers through the corresponding registries at composition.
7. No feature imports another feature directly — cross-feature work goes
   through application ports.

## Verify before merging

```bash
make lint-arch     # architecture contracts
make quality       # lint + arch + typecheck
make test-feature FEATURE=<feature_name>
```
