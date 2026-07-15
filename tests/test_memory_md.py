"""Tests for MEMORY.md generation."""

import tempfile
from pathlib import Path
from typing import Dict, List
import pytest

from cheapskate.db import Database, init_database
from cheapskate.memory_md import (
    generate_memory_md_content,
    generate_topics_section,
    generate_recent_facts_section,
    generate_quick_reference_section,
    truncate_to_size,
    MAX_MEMORY_MD_SIZE,
    MAX_RECENT_FACTS,
    MAX_TOPICS_DISPLAY,
    get_claude_memory_dir,
)


def create_sample_memories(count: int = 50) -> List[Dict]:
    """Create sample memory dicts for testing."""
    memories = []
    for i in range(count):
        memories.append({
            "id": i + 1,
            "project": "test-project",
            "timestamp": f"2025-01-{((i % 28) + 1):02d}T12:00:00",
            "accessed_at": f"2025-01-{((i % 28) + 1):02d}T12:00:00",
            "source": "agent",
            "content": f"Test memory content number {i+1}. This is a sample entry with some text.",
            "abstract": f"Abstract for memory {i+1}",
        })
    return memories


def create_sample_topics(count: int = 3) -> List[Dict]:
    """Create sample topic dicts for testing."""
    topics = []
    for i in range(count):
        topics.append({
            "id": i + 1,
            "project": "test-project",
            "name": f"Topic {i+1}",
            "summary": f"Summary for topic {i+1}\n\nWith some details.",
            "memory_ids": [1, 2, 3],
            "last_updated": "2025-01-01T00:00:00",
        })
    return topics


class TestTruncateToSize:
    """Tests for truncate_to_size function."""

    def test_content_under_limit_unchanged(self):
        """Content smaller than limit should not be truncated."""
        small_content = "# Header\n\nSome content\n"
        result = truncate_to_size(small_content, max_size=1000)
        assert result == small_content

    def test_content_over_limit_truncated(self):
        """Content over limit should be truncated."""
        large_content = "# Header\n\n" + "x" * 30000 + "\n\nMore content"
        result = truncate_to_size(large_content, max_size=1000)
        result_size = len(result.encode("utf-8"))
        assert result_size <= 1000
        assert "Truncated for size limit" in result

    def test_truncation_preserves_structure(self):
        """Truncation should keep header and topics section."""
        # Build content with Header, Topics, and lots of Recent Facts
        header = "# Memory Index\n\n_Last updated: 2025-01-01_"
        topics_header = "## Topics\n\n- [Topic 1](topics/topic-1.md)\n"
        recent_facts_header = "## Recent Facts\n\n"
        # Generate many fact lines
        facts = "\n".join(f"- Fact {i} " * 5 for i in range(100))
        content = f"{header}\n\n{topics_header}\n\n{recent_facts_header}{facts}"

        result = truncate_to_size(content, max_size=1000)
        # Header should be preserved
        assert header in result
        # Topics section should be present
        assert "## Topics" in result
        # Recent Facts section should be present but truncated
        assert "## Recent Facts" in result or "Truncated for size limit" in result

    def test_max_size_exactly_enforced(self):
        """Result should not exceed max_size (with small margin for truncation message)."""
        # Create content that's significantly over limit
        content = "x" * (MAX_MEMORY_MD_SIZE + 5000)
        result = truncate_to_size(content, max_size=MAX_MEMORY_MD_SIZE)
        encoded = result.encode("utf-8")
        # Should be <= max_size, bytes count
        assert len(encoded) <= MAX_MEMORY_MD_SIZE + 100  # small tolerance


class TestGenerateTopicsSection:
    """Tests for generate_topics_section function."""

    def test_empty_topics(self):
        """Empty topics list should produce placeholder."""
        result = generate_topics_section([])
        assert "## Topics" in result
        assert "No topics yet" in result

    def test_topics_listed(self):
        """Topics should be listed with names and descriptions."""
        topics = create_sample_topics(3)
        result = generate_topics_section(topics)
        assert "Topic 1" in result
        assert "Topic 2" in result
        assert "Topic 3" in result

    def test_topic_links_generated(self):
        """Topics should have markdown links to topic files."""
        topics = create_sample_topics(1)
        result = generate_topics_section(topics)
        assert "[Topic 1](topics/topic-1.md)" in result

    def test_max_display_limit(self):
        """Should respect MAX_TOPICS_DISPLAY limit."""
        topics = create_sample_topics(50)
        result = generate_topics_section(topics)
        # Count displayed items
        display_count = result.count("- [Topic")
        assert display_count <= MAX_TOPICS_DISPLAY

    def test_overflow_message(self):
        """Should show overflow count when topics exceed limit."""
        topics = create_sample_topics(MAX_TOPICS_DISPLAY + 5)
        result = generate_topics_section(topics)
        assert f"and {len(topics) - MAX_TOPICS_DISPLAY} more topics" in result

    def test_description_truncation(self):
        """Long topic description should be truncated."""
        topics = [{
            "id": 1,
            "project": "test",
            "name": "Long Description Topic",
            "summary": "This is a very long summary " * 10,
            "memory_ids": [],
        }]
        result = generate_topics_section(topics)
        # Description should be truncated
        assert "..." in result


class TestGenerateRecentFactsSection:
    """Tests for generate_recent_facts_section function."""

    def test_empty_memories(self):
        """Empty memories list should produce placeholder."""
        result = generate_recent_facts_section([])
        assert "## Recent Facts" in result
        assert "No memories yet" in result

    def test_memories_formatted(self):
        """Memories should be formatted as list items."""
        memories = create_sample_memories(5)
        result = generate_recent_facts_section(memories)
        # Should contain content from memories
        assert "Test memory content number 1" in result
        assert "Test memory content number 5" in result

    def test_memory_date_formatting(self):
        """Memories should show date in parentheses."""
        memories = [{
            "timestamp": "2025-01-15T12:00:00",
            "content": "A test fact",
        }]
        result = generate_recent_facts_section(memories)
        assert "(2025-01-15)" in result

    def test_max_recent_limit(self):
        """Should respect MAX_RECENT_FACTS limit."""
        memories = create_sample_memories(100)
        result = generate_recent_facts_section(memories)
        # Count bullet points
        bullet_count = result.count("- ")
        assert bullet_count <= MAX_RECENT_FACTS

    def test_overflow_message_in_facts(self):
        """Should show overflow count when memories exceed limit."""
        memories = create_sample_memories(MAX_RECENT_FACTS + 10)
        result = generate_recent_facts_section(memories)
        assert f"and {len(memories) - MAX_RECENT_FACTS} more memories" in result

    def test_long_content_truncated(self):
        """Long memory content should be truncated in index."""
        long_content = "x" * 500
        memories = [{
            "timestamp": "2025-01-01T00:00:00",
            "content": long_content,
        }]
        result = generate_recent_facts_section(memories)
        # Content should be truncated, not full length
        assert len(result) < len(long_content) * 2


class TestGenerateQuickReferenceSection:
    """Tests for generate_quick_reference_section function."""

    def test_empty_memories(self):
        """Empty memories should produce placeholder."""
        result = generate_quick_reference_section([])
        assert "## Quick Reference" in result
        assert "Run `memory topicify`" in result

    def test_commands_extracted_from_backticks(self):
        """Commands in backticks should be extracted."""
        memories = [{
            "content": "Use `git commit -m \"message\"` to commit changes."
        }]
        result = generate_quick_reference_section(memories)
        assert "git commit" in result or "git commit -m" in result

    def test_commands_deduplicated(self):
        """Duplicate commands should appear only once."""
        memories = [
            {"content": "Use `git status` to check status."},
            {"content": "Run `git status` again if needed."},
        ]
        result = generate_quick_reference_section(memories)
        count = result.count("git status")
        assert count == 1

    def test_max_commands_limit(self):
        """Should respect limit of 15 commands."""
        memories = [{"content": f"Command `cmd{i}` does something."} for i in range(30)]
        result = generate_quick_reference_section(memories)
        cmd_count = result.count("- `cmd")
        assert cmd_count <= 15


class TestGenerateMemoryMdContent:
    """Tests for generate_memory_md_content function."""

    def test_full_structure(self):
        """Generated content should have all expected sections."""
        topics = create_sample_topics(2)
        memories = create_sample_memories(3)
        result = generate_memory_md_content("test-project", topics, memories)

        # Header
        assert "# Memory Index — test-project" in result
        assert "Last updated:" in result
        # Sections
        assert "## Topics" in result
        assert "## Recent Facts" in result
        assert "## Quick Reference" in result
        # Footer
        assert "Auto-generated by Cheapskate Agent Memory" in result

    def test_empty_data(self):
        """Should handle empty topics and memories gracefully."""
        result = generate_memory_md_content("test-project", [], [])
        assert "# Memory Index — test-project" in result
        assert "No topics yet" in result
        assert "No memories yet" in result


class TestGetClaudeMemoryDir:
    """Tests for get_claude_memory_dir function."""

    def test_returns_correct_path(self):
        """Should return ~/.claude/projects/<project>/memory."""
        result = get_claude_memory_dir("my-project")
        expected = Path.home() / ".claude" / "projects" / "my-project" / "memory"
        assert result == expected


class TestMemoryMdGenerationIntegration:
    """Integration tests for generate_memory_md function."""

    def test_generate_memory_md_creates_file(self, tmp_path: Path):
        """generate_memory_md should create MEMORY.md file."""
        # Setup: create memory directory and config
        memory_dir = tmp_path / ".memory"
        memory_dir.mkdir()
        config_path = memory_dir / "config.yaml"
        config_path.write_text("""capture: {}
consolidate: {}
forgetting:
  decay_days: 90
  max_age_days: 365
  soft_delete: true
""")

        # Create a database
        db_path = memory_dir / "memory.db"
        db = init_database(db_path)

        # Add some test data
        with db.transaction() as conn:
            conn.execute(
                "INSERT INTO memories (project, source, content) VALUES (?, ?, ?)",
                ("test-project", "agent", "Test fact for index"),
            )
            conn.execute(
                "INSERT INTO memories_fts(rowid, content, project) VALUES (last_insert_rowid(), ?, ?)",
                ("Test fact for index", "test-project"),
            )
            conn.execute(
                "INSERT INTO topics (project, name, summary, memory_ids) VALUES (?, ?, ?, ?)",
                ("test-project", "Test Topic", "Summary", "[1]"),
            )

        # Call generate_memory_md
        from cheapskate.memory_md import generate_memory_md
        exit_code = generate_memory_md(
            project="test-project",
            memory_dir=memory_dir,
            force=True,
        )

        assert exit_code == 0

        # Check file exists
        expected_file = get_claude_memory_dir("test-project") / "MEMORY.md"
        assert expected_file.exists()

        # Check content
        content = expected_file.read_text()
        assert "Test fact for index" in content
        assert "Test Topic" in content

        db.close()

    def test_size_cap_enforced(self, tmp_path: Path):
        """MEMORY.md should be capped at MAX_MEMORY_MD_SIZE."""
        memory_dir = tmp_path / ".memory"
        memory_dir.mkdir()
        config_path = memory_dir / "config.yaml"
        config_path.write_text("""capture: {}
consolidate: {}
forgetting:
  decay_days: 90
  max_age_days: 365
  soft_delete: true
""")

        db_path = memory_dir / "memory.db"
        db = init_database(db_path)

        # Add many memories to ensure content is large
        with db.transaction() as conn:
            for i in range(200):
                conn.execute(
                    "INSERT INTO memories (project, source, content) VALUES (?, ?, ?)",
                    ("test-project", "agent", f"Memory {i}: " + "x" * 500),
                )
            conn.execute(
                "INSERT INTO memories_fts(rowid, content, project) SELECT id, content, project FROM memories"
            )

        from cheapskate.memory_md import generate_memory_md
        generate_memory_md(
            project="test-project",
            memory_dir=memory_dir,
            force=True,
        )

        expected_file = get_claude_memory_dir("test-project") / "MEMORY.md"
        content = expected_file.read_text()
        size = len(content.encode("utf-8"))
        assert size <= MAX_MEMORY_MD_SIZE + 100  # small tolerance

        db.close()
