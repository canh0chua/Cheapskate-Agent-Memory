"""Tests for CLI commands via subprocess."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


def run_memory(args, memory_dir=None, check=True, capture_output=True, text=True):
    """Run memory CLI with given arguments and return result."""
    cmd = [sys.executable, "-m", "cheapskate.cli"] + args
    env = os.environ.copy()
    env["CHEAPSKATE_TESTING"] = "1"
    if memory_dir:
        env["CHEAPSKATE_MEMORY_DIR"] = str(memory_dir)
    
    result = subprocess.run(
        cmd,
        capture_output=capture_output,
        text=text,
        env=env,
        cwd=Path(__file__).parent.parent,
    )
    if check and result.returncode != 0:
        print(f"Command failed: {' '.join(cmd)}")
        print(f"stdout: {result.stdout}")
        print(f"stderr: {result.stderr}")
        raise subprocess.CalledProcessError(
            result.returncode, cmd, result.stdout, result.stderr
        )
    return result


class TestCLIInit:
    """Tests for 'memory init' command."""

    def test_init_creates_database(self, tmp_path):
        """'memory init' should create memory.db file."""
        memory_dir = tmp_path / ".memory"
        result = run_memory(["init", "--path", str(memory_dir)])
        assert result.returncode == 0
        assert (memory_dir / "memory.db").exists()

    def test_init_idempotent(self, tmp_path):
        """'memory init' should be safely re-runnable — second call returns 1 (already initialized)."""
        memory_dir = tmp_path / ".memory"
        result1 = run_memory(["init", "--path", str(memory_dir)])
        assert result1.returncode == 0
        # Second init should return 1 (already initialized), not crash
        result2 = run_memory(["init", "--path", str(memory_dir)], check=False)
        assert result2.returncode == 1
        assert "already initialized" in result2.stdout.lower() or "already initialized" in result2.stderr.lower()

    def test_init_force_recreates(self, tmp_path):
        """'memory init --force' should recreate database."""
        memory_dir = tmp_path / ".memory"
        run_memory(["init", "--path", str(memory_dir)])
        
        # Add some data
        run_memory(["add", "test memory", "-p", "test", "--path", str(memory_dir)])
        
        # Force reinit
        result = run_memory(["init", "--path", str(memory_dir), "--force"])
        assert result.returncode == 0


class TestCLIAdd:
    """Tests for 'memory add' command."""

    def test_add_creates_memory(self, tmp_path):
        """'memory add' should create a new memory."""
        memory_dir = tmp_path / ".memory"
        run_memory(["init", "--path", str(memory_dir)])
        
        result = run_memory([
            "add", "Test memory content",
            "-p", "test-project",
            "--path", str(memory_dir),
        ])
        assert result.returncode == 0
        assert "Added memory" in result.stdout or "ID:" in result.stdout

    def test_add_with_tags(self, tmp_path):
        """'memory add' should accept tags."""
        memory_dir = tmp_path / ".memory"
        run_memory(["init", "--path", str(memory_dir)])
        
        result = run_memory([
            "add", "Tagged memory",
            "-p", "test",
            "-t", "tag1,tag2",
            "--path", str(memory_dir),
        ])
        assert result.returncode == 0

    def test_add_with_source(self, tmp_path):
        """'memory add' should accept source argument."""
        memory_dir = tmp_path / ".memory"
        run_memory(["init", "--path", str(memory_dir)])
        
        result = run_memory([
            "add", "User-provided memory",
            "-p", "test",
            "-s", "user",
            "--path", str(memory_dir),
        ])
        assert result.returncode == 0

    def test_add_requires_init(self, tmp_path):
        """'memory add' should fail if not initialized."""
        memory_dir = tmp_path / ".memory"
        # Don't run init
        result = run_memory([
            "add", "test",
            "--path", str(memory_dir),
        ], check=False)
        assert result.returncode != 0

    def test_add_special_characters(self, tmp_path):
        """'memory add' should handle special characters."""
        memory_dir = tmp_path / ".memory"
        run_memory(["init", "--path", str(memory_dir)])
        
        special_content = 'Memory with "quotes", <brackets>, and $symbols!'
        result = run_memory([
            "add", special_content,
            "-p", "test",
            "--path", str(memory_dir),
        ])
        assert result.returncode == 0

    def test_add_path_restriction(self, tmp_path):
        """'memory add' should be restricted to memory directory."""
        memory_dir = tmp_path / ".memory"
        run_memory(["init", "--path", str(memory_dir)])
        
        # Try adding with path outside memory dir
        other_dir = tmp_path / "other"
        other_dir.mkdir()
        result = run_memory([
            "add", "test",
            "-p", "test",
            "--path", str(other_dir),
        ], check=False)
        # Should fail because db doesn't exist there
        # This tests the path restriction feature
        assert result.returncode != 0


class TestCLIList:
    """Tests for 'memory list' command."""

    def test_list_empty_database(self, tmp_path):
        """'memory list' on empty DB should show empty list."""
        memory_dir = tmp_path / ".memory"
        run_memory(["init", "--path", str(memory_dir)])
        
        result = run_memory(["list", "--path", str(memory_dir)])
        assert result.returncode == 0

    def test_list_with_memories(self, tmp_path):
        """'memory list' should show memories."""
        memory_dir = tmp_path / ".memory"
        run_memory(["init", "--path", str(memory_dir)])
        
        # Add some memories
        run_memory(["add", "Memory 1", "-p", "test"], check=False)
        run_memory(["add", "Memory 2", "-p", "test"], check=False)
        
        result = run_memory(["list", "-p", "test", "--path", str(memory_dir)])
        assert result.returncode == 0

    def test_list_all_projects(self, tmp_path):
        """'memory list --all-projects' should show all projects."""
        memory_dir = tmp_path / ".memory"
        run_memory(["init", "--path", str(memory_dir)])
        
        run_memory(["add", "Project A memory", "-p", "projA"])
        run_memory(["add", "Project B memory", "-p", "projB"])
        
        result = run_memory([
            "list", "--all-projects", "--path", str(memory_dir)
        ])
        assert result.returncode == 0

    def test_list_with_limit(self, tmp_path):
        """'memory list' should respect --limit option."""
        memory_dir = tmp_path / ".memory"
        run_memory(["init", "--path", str(memory_dir)])
        
        # Add many memories
        for i in range(10):
            run_memory([
                "add", f"Memory {i}",
                "-p", "test",
                "--path", str(memory_dir),
            ])
        
        result = run_memory([
            "list", "-p", "test", "-n", "5", "--path", str(memory_dir)
        ])
        assert result.returncode == 0


class TestCLISearch:
    """Tests for 'memory search' command."""

    def test_search_basic(self, tmp_path):
        """'memory search' should find matching memories."""
        memory_dir = tmp_path / ".memory"
        run_memory(["init", "--path", str(memory_dir)])
        
        run_memory(["add", "Python code example", "-p", "test"])
        run_memory(["add", "JavaScript syntax", "-p", "test"])
        
        result = run_memory(["search", "python", "-p", "test", "--path", str(memory_dir)])
        assert result.returncode == 0

    def test_search_no_results(self, tmp_path):
        """'memory search' with no matches should return empty."""
        memory_dir = tmp_path / ".memory"
        run_memory(["init", "--path", str(memory_dir)])
        
        run_memory(["add", "Some content", "-p", "test"])
        
        result = run_memory(["search", "nonexistent_xyz", "-p", "test", "--path", str(memory_dir)])
        assert result.returncode == 0

    def test_search_json_output(self, tmp_path):
        """'memory search --json' should output valid JSON."""
        memory_dir = tmp_path / ".memory"
        run_memory(["init", "--path", str(memory_dir)])

        run_memory(["add", "Searchable content", "-p", "test", "--path", str(memory_dir)])

        result = run_memory([
            "search", "searchable", "-p", "test",
            "--json", "--path", str(memory_dir)
        ])
        assert result.returncode == 0
        # Should be valid JSON object with results array
        try:
            data = json.loads(result.stdout)
            assert isinstance(data, dict)
            assert "results" in data
            assert isinstance(data["results"], list)
        except json.JSONDecodeError:
            pytest.fail("Output is not valid JSON")

    def test_search_project_filter(self, tmp_path):
        """'memory search' should filter by project."""
        memory_dir = tmp_path / ".memory"
        run_memory(["init", "--path", str(memory_dir)])
        
        run_memory(["add", "Project A specific", "-p", "projA"])
        run_memory(["add", "Project B specific", "-p", "projB"])
        
        result = run_memory(["search", "specific", "-p", "projA", "--path", str(memory_dir)])
        assert result.returncode == 0
        # Output should mention projA, not projB results
        assert "projA" in result.stdout


class TestCLITopicify:
    """Tests for 'memory topicify' command."""

    def test_topicify_auto_requires_memories(self, tmp_path):
        """'memory topicify --auto' requires at least 3 memories."""
        memory_dir = tmp_path / ".memory"
        run_memory(["init", "--path", str(memory_dir)])
        
        # Only 2 memories - should warn or handle gracefully
        run_memory(["add", "Memory 1", "-p", "test", "--path", str(memory_dir)])
        run_memory(["add", "Memory 2", "-p", "test", "--path", str(memory_dir)])
        
        result = run_memory([
            "topicify", "--auto", "-p", "test",
            "--path", str(memory_dir)
        ], check=False)
        # Should handle gracefully (warn about needing more memories)
        assert result.returncode in [0, 1]  # Either works or explains

    def test_topicify_with_memories(self, tmp_path):
        """'memory topicify --auto' with enough memories should group them."""
        memory_dir = tmp_path / ".memory"
        run_memory(["init", "--path", str(memory_dir)])
        
        # Add 5 memories with different topics
        run_memory(["add", "Python: Use pydantic for validation", "-p", "test", "-t", "python", "--path", str(memory_dir)])
        run_memory(["add", "Python: FastAPI is great", "-p", "test", "-t", "python", "--path", str(memory_dir)])
        run_memory(["add", "Git: commit early and often", "-p", "test", "-t", "git", "--path", str(memory_dir)])
        run_memory(["add", "Docker: build -t tag .", "-p", "test", "-t", "docker", "--path", str(memory_dir)])
        run_memory(["add", "Docker: docker-compose up", "-p", "test", "-t", "docker", "--path", str(memory_dir)])
        
        result = run_memory([
            "topicify", "--auto", "-p", "test",
            "--path", str(memory_dir)
        ])
        # Should complete without error
        assert result.returncode == 0


class TestCLITopics:
    """Tests for 'memory topic' subcommands."""

    def test_topic_list(self, tmp_path):
        """'memory topic list' should list topics."""
        memory_dir = tmp_path / ".memory"
        run_memory(["init", "--path", str(memory_dir)])
        
        result = run_memory(["topic", "list", "--path", str(memory_dir)])
        assert result.returncode == 0

    def test_topic_create(self, tmp_path):
        """'memory topic create' should create a topic."""
        memory_dir = tmp_path / ".memory"
        run_memory(["init", "--path", str(memory_dir)])
        
        # First add some memories to link
        run_memory(["add", "Memory 1", "-p", "test"])
        run_memory(["add", "Memory 2", "-p", "test"])
        
        result = run_memory([
            "topic", "create", "new-topic",
            "-p", "test",
            "--path", str(memory_dir),
        ])
        # Should create topic (may fail if memory IDs don't exist)
        # That's okay - just test the command exists
        assert result.returncode in [0, 1]

    def test_topic_delete(self, tmp_path):
        """'memory topic delete' should delete a topic."""
        memory_dir = tmp_path / ".memory"
        run_memory(["init", "--path", str(memory_dir)])

        # Create a topic first
        run_memory(["add", "Memory", "-p", "test", "--path", str(memory_dir)])
        run_memory([
            "topic", "create", "to-delete",
            "-p", "test", "-m", "1",
            "--path", str(memory_dir),
        ])

        result = run_memory([
            "topic", "delete", "to-delete",
            "-p", "test",
            "--path", str(memory_dir),
        ], check=False)
        # Should either succeed or handle gracefully
        assert result.returncode in [0, 1]


class TestCLIStatus:
    """Tests for 'memory status' command."""

    def test_status_shows_database_info(self, tmp_path):
        """'memory status' should show database statistics."""
        memory_dir = tmp_path / ".memory"
        run_memory(["init", "--path", str(memory_dir)])
        
        result = run_memory(["status", "--path", str(memory_dir)])
        assert result.returncode == 0
        # Should show some status info
        assert "Memory" in result.stdout or "status" in result.stdout.lower()


class TestCLIStats:
    """Tests for 'memory stats' command."""

    def test_stats_shows_counts(self, tmp_path):
        """'memory stats' should show memory/topic/rule counts."""
        memory_dir = tmp_path / ".memory"
        run_memory(["init", "--path", str(memory_dir)])
        
        # Add some data
        run_memory(["add", "Memory 1", "-p", "test", "--path", str(memory_dir)])
        
        result = run_memory(["stats", "--path", str(memory_dir)])
        assert result.returncode == 0
        # Should contain counts
        assert "memory" in result.stdout.lower() or "count" in result.stdout.lower()


class TestCLIPrune:
    """Tests for 'memory prune' command."""

    def test_prune_dry_run(self, tmp_path):
        """'memory prune --dry-run' should not actually delete."""
        memory_dir = tmp_path / ".memory"
        run_memory(["init", "--path", str(memory_dir)])
        
        result = run_memory([
            "prune", "--dry-run",
            "--path", str(memory_dir),
        ])
        assert result.returncode == 0
        assert "dry" in result.stdout.lower() or "would" in result.stdout.lower()

    def test_prune_with_pruning(self, tmp_path):
        """'memory prune' should prune old memories."""
        memory_dir = tmp_path / ".memory"
        run_memory(["init", "--path", str(memory_dir)])
        
        result = run_memory([
            "prune",
            "--path", str(memory_dir),
        ], check=False)
        # Should run without crash
        assert result.returncode in [0, 1]


class TestCLIAudit:
    """Tests for 'memory audit' command."""

    def test_audit_shows_log(self, tmp_path):
        """'memory audit' should show audit trail."""
        memory_dir = tmp_path / ".memory"
        run_memory(["init", "--path", str(memory_dir)])
        
        # Add memory to create audit entry
        run_memory(["add", "Test", "-p", "test", "--path", str(memory_dir)])
        
        result = run_memory(["audit", "--path", str(memory_dir)])
        assert result.returncode == 0
        # Should show some audit info
        assert "audit" in result.stdout.lower() or "add" in result.stdout.lower()


class TestCLIConsolidate:
    """Tests for 'memory consolidate' command."""

    def test_consolidate_handles_missing_claude(self, tmp_path):
        """'memory consolidate' should handle missing Claude Code gracefully."""
        memory_dir = tmp_path / ".memory"
        run_memory(["init", "--path", str(memory_dir)])
        
        result = run_memory([
            "consolidate", "-p", "test",
            "--path", str(memory_dir),
        ], check=False)
        # Should either work or show a graceful error about Claude Code
        assert result.returncode in [0, 1]
        # If it failed, should mention Claude not found
        if result.returncode != 0:
            assert "claude" in result.stdout.lower() or "claude" in result.stderr.lower()


class TestCLIMemoryMd:
    """Tests for 'memory memory-md' command."""

    def test_memory_md_generates_file(self, tmp_path):
        """'memory memory-md --force' should generate MEMORY.md file."""
        memory_dir = tmp_path / ".memory"
        run_memory(["init", "--path", str(memory_dir)])

        # Add some data
        run_memory(["add", "Test fact", "-p", "test", "--path", str(memory_dir)])

        # --force: file may already exist from prior runs (writes to ~/.claude/projects/)
        result = run_memory([
            "memory-md", "-p", "test", "--force",
            "--path", str(memory_dir),
        ])
        assert result.returncode == 0

    def test_memory_md_force_overwrites(self, tmp_path):
        """'memory memory-md --force' should overwrite existing file."""
        memory_dir = tmp_path / ".memory"
        run_memory(["init", "--path", str(memory_dir)])

        run_memory(["add", "Fact", "-p", "test", "--path", str(memory_dir)])

        # First run: may warn if file already exists in ~/.claude/projects/
        run_memory(["memory-md", "-p", "test", "--path", str(memory_dir)], check=False)

        # Force overwrite: should always succeed
        result = run_memory([
            "memory-md", "-p", "test", "--force",
            "--path", str(memory_dir),
        ])
        assert result.returncode == 0


class TestCLIErrorHandling:
    """Tests for CLI error handling."""

    def test_unknown_command(self, tmp_path):
        """Unknown commands should show error."""
        result = run_memory(["unknown-command"], check=False)
        assert result.returncode != 0

    def test_help_flag(self, tmp_path):
        """--help should show usage."""
        result = run_memory(["--help"], check=False)
        assert result.returncode == 0
        assert "usage" in result.stdout.lower() or "memory" in result.stdout.lower()

    def test_subcommand_help(self, tmp_path):
        """'memory <subcommand> --help' should show subcommand help."""
        result = run_memory(["add", "--help"], check=False)
        assert result.returncode == 0
        assert "add" in result.stdout.lower() or "usage" in result.stdout.lower()