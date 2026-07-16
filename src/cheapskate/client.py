"""
MemoryClient — Python API for Cheapskate Agent Memory.

Usage:
    from cheapskate import MemoryClient
    mem = MemoryClient()
    mem.add("PostgreSQL on port 5432", project="myapp", tags=["infra"])
    results = mem.search("port", project="myapp")
"""

import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from cheapskate.config import Config, default_memory_dir
from cheapskate.db import Database
from cheapskate.hrr import encode, pack_vector


class MemoryClient:
    """Python API for Cheapskate Agent Memory."""

    def __init__(self, memory_dir: Optional[Path] = None):
        """
        Initialize MemoryClient.

        Args:
            memory_dir: Path to memory directory. Defaults to ~/.memory
        """
        if memory_dir is None:
            memory_dir = default_memory_dir()

        self.memory_dir = Path(memory_dir)
        self.config = Config(self.memory_dir / "config.yaml")
        self.db_path: Path = self.config.database_path
        self._db: Optional[Database] = None

    def _get_db(self) -> Database:
        """Get or create database instance."""
        if self._db is None:
            self._db = Database(self.db_path)
            self._db.connect()
        return self._db

    def close(self) -> None:
        """Close database connection."""
        if self._db:
            self._db.close()
            self._db = None

    def __enter__(self) -> "MemoryClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def init(self) -> bool:
        """
        Initialize the memory database.

        Returns:
            True if initialized successfully, False otherwise
        """
        try:
            self.memory_dir.mkdir(parents=True, exist_ok=True)
            config_path = self.memory_dir / "config.yaml"
            if not config_path.exists():
                config_path.write_text('capture:\n  auto_capture:\n    ports: true\n    errors: true\n    commands: true\n    configs: true\n    conventions: true\n  max_per_session: 50\n  tags_whitelist: []\nconsolidate:\n  schedule: "0 2 * * *"\n  trigger_threshold: 100\nforgetting:\n  decay_days: 90\n  max_age_days: 365\n  include_contradicted: false\n  soft_delete: true\nhooks:\n  on_session_start: []\n  on_error: []\n  on_file_edit: []\n  on_session_end: []\n')
            self._db = Database(self.db_path)
            self._db.init_schema()
            self._db.close()
            self._db = None
            return True
        except Exception:
            return False

    def add(
        self,
        content: str,
        project: str = "default",
        tags: Optional[List[str]] = None,
        source: str = "agent",
        confidence: Optional[float] = None,
    ) -> int:
        """
        Add a new memory.

        Args:
            content: The memory content/text to store
            project: Project name (defaults to 'default')
            tags: Optional list of tags
            source: Source of the memory (user, agent, extracted, llm_consolidate)
            confidence: Optional confidence score (0.0-1.0). Auto-set based on source if None.

        Returns:
            Memory ID

        Raises:
            RuntimeError: If memory not initialized
            ValueError: If validation fails
        """
        if not self.db_path.exists():
            raise RuntimeError("Memory not initialized. Run .init() first.")

        # Validate
        if len(content) > 10_000:
            raise ValueError(f"Content exceeds maximum length of 10000 characters")
        if len(project) > 255:
            raise ValueError(f"Project name exceeds maximum length of 255 characters")
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', project):
            raise ValueError(f"Project name must be alphanumeric, dash, or underscore only")
        if tags and len(tags) > 20:
            raise ValueError(f"Too many tags (max 20)")

        db = self._get_db()

        # Encode HRR vector
        embedding = pack_vector(encode(content))

        # Add memory
        memory_id = db.add_memory(
            project=project,
            content=content,
            source=source,
            embedding=embedding,
            tags=tags,
            confidence=confidence,
        )

        return memory_id

    def search(
        self,
        query: str,
        project: Optional[str] = None,
        all_projects: bool = False,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Search memories.

        Args:
            query: Search query
            project: Optional project name to filter by
            all_projects: If True, search all projects
            limit: Maximum number of results

        Returns:
            List of memory dicts with keys: id, project, content, source, timestamp, confidence, score
        """
        if not self.db_path.exists():
            return []

        db = self._get_db()

        if all_projects:
            project = None

        results = db.search_memories(query=query, project=project, limit=limit)
        return results

    def list(
        self,
        project: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        List memories.

        Args:
            project: Optional project name to filter by
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of memory dicts
        """
        if not self.db_path.exists():
            return []

        db = self._get_db()
        memories = db.list_memories(project=project, limit=limit, offset=offset)

        # Parse metadata/tags from each memory
        for m in memories:
            if m.get("metadata"):
                try:
                    meta = json.loads(m["metadata"])
                    m["tags"] = meta.get("tags", [])
                except Exception:
                    m["tags"] = []

        return memories

    def stats(self, project: Optional[str] = None) -> Dict[str, Any]:
        """
        Get memory statistics.

        Args:
            project: Optional project name to filter by

        Returns:
            Dict with stats: memories, topics, rules, sources, tags
        """
        if not self.db_path.exists():
            return {
                "memories": 0,
                "topics": 0,
                "rules": 0,
                "sources": {},
                "tags": {},
            }

        db = self._get_db()
        full_stats = db.get_stats()

        return full_stats

    def status(self) -> Dict[str, Any]:
        """
        Get status of the memory system.

        Returns:
            Dict with initialized flag, paths, stats, config summary
        """
        if not self.db_path.exists():
            return {
                "initialized": False,
                "memory_dir": str(self.memory_dir),
                "database_path": str(self.db_path),
            }

        db = self._get_db()
        stats = db.get_stats()

        last_consolidate = db.get_state("last_consolidate_default")
        last_prune = db.get_state("last_prune")

        config_summary = {
            "capture": {
                "auto_capture": {
                    "ports": self.config.get("capture.auto_capture.ports", True),
                    "errors": self.config.get("capture.auto_capture.errors", True),
                    "commands": self.config.get("capture.auto_capture.commands", True),
                    "configs": self.config.get("capture.auto_capture.configs", True),
                    "conventions": self.config.get("capture.auto_capture.conventions", True),
                },
                "max_per_session": self.config.get("capture.max_per_session", 50),
                "tags_whitelist": self.config.get("capture.tags_whitelist", []),
            },
            "consolidate": {
                "schedule": self.config.get("consolidate.schedule", "0 2 * * *"),
                "trigger_threshold": self.config.get("consolidate.trigger_threshold", 100),
            },
            "forgetting": {
                "decay_days": self.config.get("forgetting.decay_days", 90),
                "max_age_days": self.config.get("forgetting.max_age_days", 365),
            },
        }

        return {
            "initialized": True,
            "memory_dir": str(self.memory_dir),
            "database_path": str(self.db_path),
            "stats": stats,
            "last_consolidate": last_consolidate,
            "last_prune": last_prune,
            "config": config_summary,
        }

    def topicify(
        self,
        project: Optional[str] = None,
        auto: bool = False,
        group_by: str = "tags",
    ) -> Dict[str, Any]:
        """
        Organize memories into topics.

        Args:
            project: Project name (auto-detected if None)
            auto: Use auto mode (combine tags + similarity)
            group_by: How to group: "tags", "vector", "keywords", or "auto"

        Returns:
            Dict with topics and statistics
        """
        import subprocess, sys

        if project is None:
            project = "default"

        cmd = [sys.executable, "-m", "cheapskate.cli", "topicify", "--project", project]
        if auto:
            cmd.append("--auto")
        if group_by != "tags":
            cmd.extend(["--group-by", group_by])

        result = subprocess.run(cmd, capture_output=True, text=True, env=os.environ.copy())
        return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}

    def consolidate(self, project: Optional[str] = None) -> Dict[str, Any]:
        """
        Consolidate memories using LLM synthesis.

        Note: This requires a configured LLM backend (claude, ollama, or offline).

        Args:
            project: Project name (defaults to 'default' if None)

        Returns:
            Dict with keys: returncode, stdout, stderr
        """
        import subprocess

        if project is None:
            project = "default"

        cmd = [sys.executable, "-m", "cheapskate.cli", "consolidate", "--project", project]
        result = subprocess.run(cmd, capture_output=True, text=True, env=os.environ.copy())
        return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}