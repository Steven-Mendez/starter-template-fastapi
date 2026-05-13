## ADDED Requirements

### Requirement: Production Docker image is hardened

The production `Dockerfile` SHALL:

- Pin base images by `@sha256:<digest>` for both `python` and the `uv` source image. Renovate config SHALL track these digests.
- Create the runtime user with explicit `--uid 10001 --gid 10001`.
- Install `tini` and set `ENTRYPOINT ["tini", "--"]` so SIGCHLD reaping works for any child processes.
- `.dockerignore` SHALL exclude `var/`, `.github/`, `openspec/`, `scripts/`, `reports/`, `.DS_Store`, `*.log`, `tmp/`.

#### Scenario: Container runs as the documented UID

- **GIVEN** the image built from the production Dockerfile
- **WHEN** the container starts and shells `id -u`
- **THEN** the output is `10001`

#### Scenario: Base images are digest-pinned

- **WHEN** the `Dockerfile` is read
- **THEN** every `FROM …` and `COPY --from=…` references either a SHA-256 digest or a builder stage name

#### Scenario: Container refuses to run as root

- **GIVEN** the image built from the production Dockerfile
- **WHEN** the container starts under a `runAsNonRoot: true` policy (or the operator inspects the final `USER` directive)
- **THEN** the effective UID is non-zero (`id -u != 0`)
- **AND** writing to read-only locations such as `/etc` fails with permission denied

#### Scenario: tini reaps zombie children

- **GIVEN** the image built from the production Dockerfile
- **WHEN** the container has run any subprocess (e.g. the HEALTHCHECK's `python -c ...`) that exits
- **THEN** PID 1 is `tini` (not `uvicorn`)
- **AND** no defunct (`<defunct>` / Z-state) processes accumulate over time
