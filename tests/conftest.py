"""Pytest configuration and shared fixtures for Cheapskate Agent Memory tests."""

import os
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import patch

import pytest

from cheapskate.config import Config
from cheapskate.db import Database, init_database


# Skip monkeypatch approach — config.py now respects CHEAPSKATE_TESTING env var.
# Set it globally so all imports of validate_memory_path use the permissive version.

import os
os.environ["CHEAPSKATE_TESTING"] = "1"


@pytest.fixture
def temp_db(tmp_path: Path) -> Generator[Database, None, None]:
    """Create a temporary database for each test."""
    db_path = tmp_path / "test_memory.db"
    db = init_database(db_path)
    yield db
    db.close()


@pytest.fixture
def temp_memory_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary memory directory with config.yaml."""
    memory_dir = tmp_path / ".memory"
    memory_dir.mkdir(parents=True, exist_ok=True)

    # Create a basic config file
    config_path = memory_dir / "config.yaml"
    config_content = """capture:
  auto_capture:
    ports: true
    errors: true
    commands: true
    configs: true
    conventions: true
  max_per_session: 50
  tags_whitelist: []
consolidate:
  schedule: "0 2 * * *"
  trigger_threshold: 100
forgetting:
  decay_days: 90
  max_age_days: 365
  include_contradicted: false
  soft_delete: true
"""
    config_path.write_text(config_content)
    yield memory_dir


@pytest.fixture
def config(temp_memory_dir: Path) -> Config:
    """Load config from the temporary memory directory."""
    config_path = temp_memory_dir / "config.yaml"
    return Config(config_path=config_path)


@pytest.fixture
def db_with_sample_data(temp_db: Database) -> Generator[Database, None, None]:
    """Create a database with sample memories for testing."""
    with temp_db.transaction() as conn:
        # Add some test memories
        conn.execute(
            "INSERT INTO memories (project, source, content, metadata) VALUES (?, ?, ?, ?)",
            ("test-project", "agent", "Test memory one", '{"tags": ["test", "one"]}'),
        )
        conn.execute(
            "INSERT INTO memories (project, source, content, metadata) VALUES (?, ?, ?, ?)",
            ("test-project", "user", "Test memory two", '{"tags": ["test", "two"]}'),
        )
        conn.execute(
            "INSERT INTO memories (project, source, content, metadata) VALUES (?, ?, ?, ?)",
            ("other-project", "agent", "Another memory", '{"tags": ["other"]}'),
        )
        # Update FTS
        conn.execute("INSERT INTO memories_fts(rowid, content, project) SELECT id, content, project FROM memories")
    yield temp_db
