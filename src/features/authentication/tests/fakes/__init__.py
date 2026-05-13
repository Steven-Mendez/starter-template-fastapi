"""Test fakes for auth use-case unit tests."""

from features.authentication.tests.fakes.fake_auth_repository import (
    FakeAuthRepository,
)
from features.authentication.tests.fakes.fake_clock import FakeClock
from features.authentication.tests.fakes.fake_id_generator import FakeIdGenerator

__all__ = ["FakeAuthRepository", "FakeClock", "FakeIdGenerator"]
