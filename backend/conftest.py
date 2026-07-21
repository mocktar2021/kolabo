"""Test configuration.

Force an in memory SQLite database for the test suite so tests do not require a
running PostgreSQL instance. A CI job that provides its own DATABASE_URL still
takes precedence because setdefault does not overwrite an existing value.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
