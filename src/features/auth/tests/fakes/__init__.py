"""Test fakes for auth use-case unit tests."""

from src.features.auth.tests.fakes.fake_auth_repository import FakeAuthRepository
from src.features.auth.tests.fakes.fake_clock import FakeClock
from src.features.auth.tests.fakes.fake_id_generator import FakeIdGenerator

__all__ = ["FakeAuthRepository", "FakeClock", "FakeIdGenerator"]
