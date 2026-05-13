"""Unit tests for the ``CredentialRepositoryPort`` contract.

The same scenarios are exercised against the real SQLModel adapter in
``tests/integration/test_credentials_repository_postgres.py``.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from features.authentication.tests.fakes import FakeAuthRepository

pytestmark = pytest.mark.unit


def test_get_credential_returns_none_when_user_has_no_credential() -> None:
    repo = FakeAuthRepository()

    assert repo.get_credential_for_user(uuid4()) is None


def test_upsert_inserts_then_replaces_in_place() -> None:
    repo = FakeAuthRepository()
    user_id = uuid4()

    inserted = repo.upsert_credential(
        user_id=user_id, algorithm="argon2", hash="hash-v1"
    )
    fetched = repo.get_credential_for_user(user_id)
    assert fetched == inserted

    replaced = repo.upsert_credential(
        user_id=user_id, algorithm="argon2", hash="hash-v2"
    )
    # Same row id (in-place update); only the hash and last_changed_at differ.
    assert replaced.id == inserted.id
    assert replaced.hash == "hash-v2"
    assert replaced.last_changed_at >= inserted.last_changed_at
    assert repo.get_credential_for_user(user_id) == replaced


def test_credentials_are_keyed_by_algorithm() -> None:
    repo = FakeAuthRepository()
    user_id = uuid4()

    argon = repo.upsert_credential(
        user_id=user_id, algorithm="argon2", hash="argon-hash"
    )
    bcrypt = repo.upsert_credential(
        user_id=user_id, algorithm="bcrypt", hash="bcrypt-hash"
    )

    assert argon.id != bcrypt.id
    assert repo.get_credential_for_user(user_id, algorithm="argon2") == argon
    assert repo.get_credential_for_user(user_id, algorithm="bcrypt") == bcrypt
