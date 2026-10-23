"""Fixtures for the test suite proper. The root conftest.py keeps the ones
that have to run before anything imports the app.

ONE JOB SO FAR: the rate limiter's counters live in module memory (see
app/core/ratelimit.py for why), and memory is shared by every test in a
session. Without this, the suite's own traffic accumulates against the single
address TestClient presents, the forty-first login in a run gets a 429 that
has nothing to do with the test that triggered it, and which test fails
depends on the order they happened to run in. Resetting before each test is
what keeps a limit test meaningful and every other test oblivious.
"""
import pytest

from app.core import ratelimit


@pytest.fixture(autouse=True)
def fresh_rate_limits():
    ratelimit.reset()
    yield
    ratelimit.reset()
