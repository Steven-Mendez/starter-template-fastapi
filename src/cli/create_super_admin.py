"""CLI: create or promote the first ``system:main#admin``.

This module is a project-level composition root (a peer of
``main.py`` and ``worker.py``). It assembles the same feature
containers the web app uses so the bootstrap path exercises the
exact wiring the production processes do, without duplicating the
wiring code.

Running as a CLI avoids a chicken-and-egg situation where creating
the first admin would otherwise require an admin JWT to already
exist. Configuration is read from the standard ``APP_*`` environment
variables; the password is read from a named environment variable
to keep it out of shell history and process listings.

Invocation::

    uv run python -m cli.create_super_admin create-super-admin \\
        --email admin@example.com \\
        --password-env AUTH_BOOTSTRAP_PASSWORD
"""

from __future__ import annotations

import argparse
import os

from app_platform.config.settings import AppSettings
from features.authentication.adapters.outbound.persistence.sqlmodel import (
    SQLModelAuthRepository,
)
from features.authentication.composition.container import (
    AuthContainer,
    build_auth_container,
)
from features.authentication.email_templates import (
    register_authentication_email_templates,
)
from features.authorization.composition import (
    AuthorizationContainer,
    build_authorization_container,
)
from features.background_jobs.composition.container import (
    JobsContainer,
    build_jobs_container,
)
from features.background_jobs.composition.settings import JobsSettings
from features.email.composition.container import (
    EmailContainer,
    build_email_container,
)
from features.email.composition.jobs import register_send_email_handler
from features.email.composition.settings import EmailSettings
from features.outbox.composition.container import build_outbox_container
from features.outbox.composition.handler_dedupe import build_handler_dedupe
from features.outbox.composition.settings import OutboxSettings
from features.users.composition.container import (
    UsersContainer,
    build_user_registrar_adapter,
    build_users_container,
)


def _build_containers() -> tuple[
    AuthContainer,
    UsersContainer,
    AuthorizationContainer,
    EmailContainer,
    JobsContainer,
]:
    """Construct auth + users + authorization + email + jobs containers from env.

    Wiring mirrors ``main.py``: each feature is assembled through its
    public ``composition/container.py`` API so the CLI exercises the
    same dependency graph the web app does. The authorization
    registry is sealed before the bootstrap use case runs so a stray
    runtime ``register_*`` call surfaces as a clear error.
    """
    settings = AppSettings()
    repository = SQLModelAuthRepository(
        settings.postgresql_dsn,
        create_schema=False,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=settings.db_pool_recycle_seconds,
        pool_pre_ping=settings.db_pool_pre_ping,
    )
    users = build_users_container(engine=repository.engine)
    email = build_email_container(
        EmailSettings.from_app_settings(
            backend=settings.email_backend,
            from_address=settings.email_from,
            smtp_host=settings.email_smtp_host,
            smtp_port=settings.email_smtp_port,
            smtp_username=settings.email_smtp_username,
            smtp_password=settings.email_smtp_password,
            smtp_use_starttls=settings.email_smtp_use_starttls,
            smtp_use_ssl=settings.email_smtp_use_ssl,
            smtp_timeout_seconds=settings.email_smtp_timeout_seconds,
        )
    )
    register_authentication_email_templates(email.registry)
    email.registry.seal()
    jobs = build_jobs_container(
        JobsSettings.from_app_settings(
            backend=settings.jobs_backend,
            redis_url=settings.jobs_redis_url or settings.auth_redis_url,
            queue_name=settings.jobs_queue_name,
        )
    )
    outbox = build_outbox_container(
        OutboxSettings.from_app_settings(settings),
        engine=repository.engine,
        job_queue=jobs.port,
    )
    register_send_email_handler(
        jobs.registry,
        email.port,
        dedupe=build_handler_dedupe(repository.engine),
    )
    jobs.registry.seal()
    auth = build_auth_container(
        settings=settings,
        users=users.user_repository,
        outbox_uow=outbox.unit_of_work,
        repository=repository,
    )
    user_registrar = build_user_registrar_adapter(
        users=users, credential_writer=auth.credential_writer_adapter
    )
    authorization = build_authorization_container(
        engine=repository.engine,
        user_authz_version=users.user_authz_version_adapter,
        user_registrar=user_registrar,
        audit=auth.audit_adapter,
    )
    # Seal the authorization registry so the bootstrap use case runs
    # against the exact same frozen graph that the live application
    # sees. The previous ``management.py`` never sealed the registry —
    # the live app catches stray registrations only because it seals
    # in its lifespan. ``seal()`` is idempotent, so calling it here is
    # safe even if a caller (or a test) has already sealed.
    authorization.registry.seal()
    return auth, users, authorization, email, jobs


def create_super_admin(email: str, password_env: str) -> None:
    """Create or promote a user to ``system:main#admin``.

    Args:
        email: Email address of the system admin account to create or promote.
        password_env: Name of the environment variable holding the password.
            Reading the password from the environment rather than as a CLI
            argument prevents it from appearing in shell history or process
            listings.

    Raises:
        SystemExit: If the password environment variable is not set.
    """
    password = os.getenv(password_env)
    if not password:
        raise SystemExit(f"Environment variable {password_env} is required")
    auth, users, authorization, _email, jobs = _build_containers()
    try:
        authorization.bootstrap_system_admin.execute(email=email, password=password)
    finally:
        authorization.shutdown()
        jobs.shutdown()
        users.shutdown()
        auth.shutdown()


def main() -> None:
    """Entry point for the bootstrap-admin CLI."""
    parser = argparse.ArgumentParser(
        description="Project-level CLI for one-shot bootstrap operations",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    super_admin = subparsers.add_parser(
        "create-super-admin",
        # Kept as a CLI command rather than an API endpoint so that
        # creating the first admin does not require an admin token to
        # exist yet.
        help="Create or promote the first system admin via a non-public command",
    )
    super_admin.add_argument("--email", required=True)
    super_admin.add_argument("--password-env", default="AUTH_BOOTSTRAP_PASSWORD")

    args = parser.parse_args()
    if args.command == "create-super-admin":
        create_super_admin(args.email, args.password_env)


if __name__ == "__main__":
    main()
