## 1. Digest pin

- [ ] 1.1 Replace `FROM python:3.12-slim` with `FROM python:3.12-slim@sha256:<digest>`. Pick the current digest at the time of the PR.
- [ ] 1.2 Replace `COPY --from=ghcr.io/astral-sh/uv:0.11.8 …` with `COPY --from=ghcr.io/astral-sh/uv:0.11.8@sha256:<digest> …`.
- [ ] 1.3 Add a Renovate `packageRules` entry so digest bumps are picked up (`updatePinnedDependencies: true`).

## 2. Explicit UID/GID

- [ ] 2.1 In the runtime stage: `addgroup --system --gid 10001 app && adduser --system --uid 10001 --ingroup app app`.
- [ ] 2.2 Document in `docs/operations.md` the required `runAsUser: 10001` / `fsGroup: 10001` in K8s manifests.

## 3. tini

- [ ] 3.1 Add `apt-get install -y --no-install-recommends tini` to the runtime stage.
- [ ] 3.2 Set `ENTRYPOINT ["tini", "--"]`; leave the `CMD` as-is.

## 4. `.dockerignore`

- [ ] 4.1 Append the following entries to `.dockerignore` (one per line): `var/`, `.github/`, `openspec/`, `scripts/`, `reports/`, `.DS_Store`, `*.log`, `tmp/`. (`reports/` already exists; skip the duplicate.)

## 5. Verify

- [ ] 5.1 Build the image (`docker build --target runtime -t starter-api:hardened .`) and confirm it boots.
- [ ] 5.2 Run `docker run --rm starter-api:hardened id -u` and assert the output is `10001`.
- [ ] 5.3 Run the container with `--read-only` (rootless verification) and confirm it cannot write to `/etc`.
- [ ] 5.4 Verify SIGTERM produces a graceful exit (combined with `add-graceful-shutdown`).
- [ ] 5.5 `make ci` green.
