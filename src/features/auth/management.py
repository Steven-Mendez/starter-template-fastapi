"""Management CLI for the auth feature.

Exposes one-shot operations that should not be reachable from the public
API. Currently a single subcommand: ``create-super-admin`` writes the
``system:main#admin`` relationship tuple for the configured account.
Running as a CLI avoids a chicken-and-egg situation where creating
the first admin would otherwise require an admin JWT to already exist.
"""

from __future__ import annotations

import argparse
import os

from src.features.auth.composition.container import AuthContainer, build_auth_container
from src.platform.config.settings import AppSettings


def _build_container() -> AuthContainer:
    """Construct an auth container from the current environment settings."""
    settings = AppSettings()
    return build_auth_container(settings=settings)


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
    container = _build_container()
    try:
        container.bootstrap_system_admin.execute(email=email, password=password)
    finally:
        container.shutdown()


def main() -> None:
    """Entry point for the auth management CLI."""
    parser = argparse.ArgumentParser(description="Auth management commands")
    subparsers = parser.add_subparsers(dest="command", required=True)

    super_admin = subparsers.add_parser(
        "create-super-admin",
        # Kept as a management command rather than an API endpoint so that
        # creating the first admin does not require an admin token to exist yet.
        help="Create or promote the first system admin via a non-public command",
    )
    super_admin.add_argument("--email", required=True)
    super_admin.add_argument("--password-env", default="AUTH_BOOTSTRAP_PASSWORD")

    args = parser.parse_args()
    if args.command == "create-super-admin":
        create_super_admin(args.email, args.password_env)


if __name__ == "__main__":
    main()
