"""Management CLI for the auth feature.

Exposes one-shot operations that should not be reachable from the public
API (seeding default RBAC data, bootstrapping the first ``super_admin``).
Running them as a CLI avoids a chicken-and-egg situation where creating
the first admin would otherwise require an admin token to already exist.
"""

from __future__ import annotations

import argparse
import os

from src.features.auth.adapters.outbound.persistence.sqlmodel import (
    SQLModelAuthRepository,
)
from src.features.auth.composition.container import AuthContainer, build_auth_container
from src.platform.config.settings import AppSettings


def _build_container() -> tuple[SQLModelAuthRepository, AuthContainer]:
    """Construct a repository and auth container from the current environment settings.

    Returns:
        A tuple of ``(repository, AuthContainer)`` ready for use.
        The caller is responsible for calling ``repository.close()`` when done.
    """
    settings = AppSettings()
    repository = SQLModelAuthRepository(settings.postgresql_dsn, create_schema=False)
    return repository, build_auth_container(settings=settings, repository=repository)


def seed() -> None:
    """Seed the database with the default roles and permissions.

    Idempotent: safe to run multiple times without duplicating data.
    Uses the database URL from ``AppSettings`` (environment / .env file).
    """
    repository, container = _build_container()
    try:
        container.seed_initial_data.execute()
    finally:
        repository.close()


def create_super_admin(email: str, password_env: str) -> None:
    """Create or promote a user to the ``super_admin`` role.

    Seeds roles and permissions first if they have not been seeded yet.

    Args:
        email: Email address of the super admin account to create or promote.
        password_env: Name of the environment variable that holds the password.
            The password is read from the environment rather than passed as an
            argument to avoid exposure in shell history or process listings.

    Raises:
        SystemExit: If the password environment variable is not set.
    """
    # Reading the password from an environment variable rather than a CLI
    # argument prevents it from appearing in shell history or process listings.
    password = os.getenv(password_env)
    if not password:
        raise SystemExit(f"Environment variable {password_env} is required")
    repository, container = _build_container()
    try:
        container.bootstrap_super_admin.execute(
            email=email,
            password=password,
        )
    finally:
        repository.close()


def main() -> None:
    """Entry point for the auth/RBAC management CLI.

    Subcommands:
        seed: Populate the database with default roles and permissions.
        create-super-admin: Create or promote the first super_admin account.
    """
    parser = argparse.ArgumentParser(description="Auth/RBAC management commands")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("seed", help="Seed initial roles and permissions")

    super_admin = subparsers.add_parser(
        "create-super-admin",
        # Kept as a management command rather than an API endpoint so that
        # creating the first admin does not require an admin token to exist yet.
        help="Create or promote the first super_admin through a non-public command",
    )
    super_admin.add_argument("--email", required=True)
    super_admin.add_argument("--password-env", default="AUTH_BOOTSTRAP_PASSWORD")

    args = parser.parse_args()
    if args.command == "seed":
        seed()
    elif args.command == "create-super-admin":
        create_super_admin(args.email, args.password_env)


if __name__ == "__main__":
    main()
