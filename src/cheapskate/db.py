"""
Database module for Cheapskate Agent Memory.

Manages SQLite database with FTS5 full-text search support.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cheapskate.config import default_memory_dir


class Database:
    """SQLite database manager for Cheapskate Agent Memory."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or default_memory_dir() / "memory.db"
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self.conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
        return self.conn

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    @contextmanager
    def transaction(self):
        """Context manager for database transactions."""
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def init_schema(self) -> None:
        """Initialize the database schema."""
        conn = self.connect()

        # Enable FTS5
        conn.execute("PRAGMA journal_mode=WAL")

        # Create memories table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                accessed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                source TEXT NOT NULL CHECK(source IN ('user', 'agent', 'extracted', 'llm_consolidate')),
                content TEXT NOT NULL,
                embedding BLOB,
                metadata TEXT,
                contradicted_by INTEGER REFERENCES memories(id),
                created DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create FTS5 virtual table
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                content,
                project,
                content=memories,
                content_rowid=id
            )
        """)

        # Create topics table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project TEXT NOT NULL,
                name TEXT NOT NULL,
                summary TEXT,
                memory_ids TEXT,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(project, name)
            )
        """)

        # Create rules table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project TEXT NOT NULL,
                scope TEXT NOT NULL CHECK(scope IN ('global', 'user', 'project', 'local')),
                content TEXT NOT NULL,
                priority INTEGER DEFAULT 0
            )
        """)

        # Create audit table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id INTEGER REFERENCES memories(id),
                action TEXT NOT NULL CHECK(action IN ('add', 'update', 'prune', 'contradict', 'access')),
                reason TEXT,
                agent_id TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """)

        # State table for consolidation timestamps etc.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS state (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_project ON memories(project)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_accessed ON memories(accessed_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_source ON memories(source)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_topics_project ON topics(project)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rules_project_scope ON rules(project, scope)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_memory ON audit(memory_id)")

        conn.commit()

    def add_memory(
        self,
        project: str,
        content: str,
        source: str = "agent",
        embedding: Optional[bytes] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> int:
        """Add a new memory entry."""
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO memories (project, source, content, embedding, metadata)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    project,
                    source,
                    content,
                    embedding,
                    json.dumps(metadata or {"tags": tags or []}),
                ),
            )
            memory_id = cursor.lastrowid

            # Add to FTS index
            conn.execute(
                "INSERT INTO memories_fts(rowid, content, project) VALUES (?, ?, ?)",
                (memory_id, content, project),
            )

            # Log audit
            conn.execute(
                "INSERT INTO audit (memory_id, action, reason) VALUES (?, 'add', 'manual')",
                (memory_id,),
            )

            return memory_id

    def list_memories(
        self,
        project: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List memory entries, optionally filtered by project."""
        conn = self.connect()
        if project:
            cursor = conn.execute(
                """
                SELECT id, project, timestamp, source, content, accessed_at
                FROM memories
                WHERE project = ?
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
                """,
                (project, limit, offset),
            )
        else:
            cursor = conn.execute(
                """
                SELECT id, project, timestamp, source, content, accessed_at
                FROM memories
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def search_memories(
        self,
        query: str,
        project: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Full-text search on memories using FTS5."""
        conn = self.connect()

        # Sanitize query for FTS5
        fts_query = self._sanitize_fts_query(query)

        if project:
            cursor = conn.execute(
                """
                SELECT m.id, m.project, m.timestamp, m.source, m.content, m.accessed_at,
                       rank
                FROM memories m
                JOIN memories_fts fts ON m.id = fts.rowid
                WHERE memories_fts MATCH ?
                  AND m.project = ?
                ORDER BY rank
                LIMIT ?
                """,
                (fts_query, project, limit),
            )
        else:
            cursor = conn.execute(
                """
                SELECT m.id, m.project, m.timestamp, m.source, m.content, m.accessed_at,
                       rank
                FROM memories m
                JOIN memories_fts fts ON m.id = fts.rowid
                WHERE memories_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (fts_query, limit),
            )

        rows = cursor.fetchall()

        # Update accessed_at for retrieved memories
        now = datetime.utcnow().isoformat()
        for row in rows:
            conn.execute(
                "UPDATE memories SET accessed_at = ? WHERE id = ?",
                (now, row["id"]),
            )

        return [dict(row) for row in rows]

    def _sanitize_fts_query(self, query: str) -> str:
        """Sanitize user input for FTS5 query."""
        # Escape special FTS5 characters and wrap for prefix search
        # Split into words and add * suffix for prefix matching
        words = query.split()
        sanitized_words = []
        for word in words:
            # Remove FTS5 special characters
            clean = "".join(c for c in word if c.isalnum() or c.isspace())
            if clean:
                sanitized_words.append(clean + "*")
        return " ".join(sanitized_words)

    def get_memory(self, memory_id: int) -> Optional[Dict[str, Any]]:
        """Get a single memory by ID."""
        conn = self.connect()
        cursor = conn.execute(
            "SELECT * FROM memories WHERE id = ?",
            (memory_id,),
        )
        row = cursor.fetchone()
        if row:
            result = dict(row)
            if result.get("metadata"):
                result["metadata"] = json.loads(result["metadata"])
            return result
        return None

    def delete_memory(self, memory_id: int) -> bool:
        """Delete a memory entry."""
        with self.transaction() as conn:
            # Delete from FTS
            conn.execute("DELETE FROM memories_fts WHERE rowid = ?", (memory_id,))
            # Delete from main table
            cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            return cursor.rowcount > 0

    def upsert_topic(
        self,
        project: str,
        name: str,
        summary: Optional[str] = None,
        memory_ids: Optional[List[int]] = None,
    ) -> int:
        """Insert or update a topic. Returns topic ID."""
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO topics (project, name, summary, memory_ids, last_updated)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(project, name) DO UPDATE SET
                    summary = excluded.summary,
                    memory_ids = excluded.memory_ids,
                    last_updated = CURRENT_TIMESTAMP
                """,
                (project, name, summary, json.dumps(memory_ids or [])),
            )
            return cursor.lastrowid or conn.execute(
                "SELECT id FROM topics WHERE project = ? AND name = ?",
                (project, name)
            ).fetchone()["id"]

    def get_topics(self, project: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all topics, optionally filtered by project."""
        conn = self.connect()
        if project:
            cursor = conn.execute(
                "SELECT * FROM topics WHERE project = ? ORDER BY name",
                (project,),
            )
        else:
            cursor = conn.execute("SELECT * FROM topics ORDER BY project, name")
        rows = cursor.fetchall()
        results = []
        for row in rows:
            result = dict(row)
            if result.get("memory_ids"):
                result["memory_ids"] = json.loads(result["memory_ids"])
            results.append(result)
        return results

    def get_topic(self, project: str, name: str) -> Optional[Dict[str, Any]]:
        """Get a single topic by project and name."""
        conn = self.connect()
        cursor = conn.execute(
            "SELECT * FROM topics WHERE project = ? AND name = ?",
            (project, name),
        )
        row = cursor.fetchone()
        if row:
            result = dict(row)
            if result.get("memory_ids"):
                result["memory_ids"] = json.loads(result["memory_ids"])
            return result
        return None

    def delete_topic(self, project: str, name: str) -> bool:
        """Delete a topic by project and name."""
        with self.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM topics WHERE project = ? AND name = ?",
                (project, name),
            )
            return cursor.rowcount > 0

    def get_stats(self) -> Dict[str, int]:
        """Get database statistics."""
        conn = self.connect()
        cursor = conn.execute("SELECT COUNT(*) as count FROM memories")
        memories_count = cursor.fetchone()["count"]

        cursor = conn.execute("SELECT COUNT(*) as count FROM topics")
        topics_count = cursor.fetchone()["count"]

        cursor = conn.execute("SELECT COUNT(*) as count FROM rules")
        rules_count = cursor.fetchone()["count"]

        return {
            "memories": memories_count,
            "topics": topics_count,
            "rules": rules_count,
        }

    # ------------------------------------------------------------------
    # Phase 4 helpers
    # ------------------------------------------------------------------
    def prune_memories(
        self,
        project: Optional[str] = None,
        decay_days: int = 90,
        max_age_days: int = 365,
        soft_delete: bool = True,
        dry_run: bool = False,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Prune memories based on forgetting config.

        Returns a summary dict with counts and affected memory IDs.
        """
        conn = self.connect()
        now = datetime.utcnow()
        pruned: List[int] = []

        # Decay pruning: accessed_at older than decay_days
        if decay_days > 0:
            cutoff = (now - timedelta(days=decay_days)).isoformat()
            if project:
                cursor = conn.execute(
                    "SELECT id FROM memories WHERE project = ? AND accessed_at < ?",
                    (project, cutoff),
                )
            else:
                cursor = conn.execute(
                    "SELECT id FROM memories WHERE accessed_at < ?",
                    (cutoff,),
                )
            decay_ids = [row["id"] for row in cursor.fetchall()]
            pruned.extend(decay_ids)

        # Max age pruning: timestamp older than max_age_days
        if max_age_days > 0:
            cutoff = (now - timedelta(days=max_age_days)).isoformat()
            if project:
                cursor = conn.execute(
                    "SELECT id FROM memories WHERE project = ? AND timestamp < ?",
                    (project, cutoff),
                )
            else:
                cursor = conn.execute(
                    "SELECT id FROM memories WHERE timestamp < ?",
                    (cutoff,),
                )
            age_ids = [row["id"] for row in cursor.fetchall()]
            # Union while preserving order
            for aid in age_ids:
                if aid not in pruned:
                    pruned.append(aid)

        if dry_run:
            return {
                "dry_run": True,
                "would_prune_count": len(pruned),
                "memory_ids": pruned,
            }

        # Perform deletion / soft-delete
        deleted_count = 0
        for memory_id in pruned:
            if soft_delete:
                # Remove from FTS to hide from queries, but keep row
                conn.execute("DELETE FROM memories_fts WHERE rowid = ?", (memory_id,))
                conn.execute(
                    "UPDATE memories SET content = '[pruned]' WHERE id = ?",
                    (memory_id,),
                )
            else:
                conn.execute("DELETE FROM memories_fts WHERE rowid = ?", (memory_id,))
                conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            conn.execute(
                "INSERT INTO audit (memory_id, action, reason, agent_id) VALUES (?, 'prune', 'decay/max_age', ?)",
                (memory_id, agent_id),
            )
            deleted_count += 1

        return {
            "dry_run": False,
            "pruned_count": deleted_count,
            "memory_ids": pruned,
        }

    def get_audit_trail(
        self,
        project: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Return recent audit entries, optionally filtered."""
        conn = self.connect()
        query = """
            SELECT a.id, a.memory_id, a.action, a.reason, a.agent_id, a.timestamp, a.metadata,
                   m.project, m.content
            FROM audit a
            LEFT JOIN memories m ON m.id = a.memory_id
        """
        params: List[Any] = []
        clauses: List[str] = []
        if project:
            clauses.append("m.project = ?")
            params.append(project)
        if action:
            clauses.append("a.action = ?")
            params.append(action)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY a.timestamp DESC LIMIT ?"
        params.append(limit)

        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        results = []
        for row in rows:
            result = dict(row)
            if result.get("metadata"):
                try:
                    result["metadata"] = json.loads(result["metadata"])
                except Exception:
                    pass
            results.append(result)
        return results

    def set_state(self, key: str, value: str) -> None:
        """Set a state key/value."""
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO state (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
                """,
                (key, value),
            )

    def get_state(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a state value."""
        conn = self.connect()
        cursor = conn.execute("SELECT value FROM state WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else default


    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def init_database(db_path: Optional[Path] = None) -> Database:
    """Initialize database with schema."""
    db = Database(db_path)
    db.init_schema()
    return db


def get_database(db_path: Optional[Path] = None) -> Database:
    """Get database instance, initialized if needed."""
    db = Database(db_path)
    db.connect()
    return db