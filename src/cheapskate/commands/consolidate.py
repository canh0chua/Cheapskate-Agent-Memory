"""
memory consolidate command - Dreams-style consolidation via Claude Code CLI.
"""

import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from cheapskate.config import Config, default_memory_dir
from cheapskate.db import Database


DREAMS_PROMPT = """You are a memory curator. Below are new memories added since last consolidation.

{memories}

Tasks:
1. For each existing topic, integrate new facts.
2. Create new topics if needed.
3. Detect and resolve contradictions.
4. Rewrite each topic file to be concise and useful.
5. Update MEMORY.md index (stay under 25KB).

Output: updated topic files + MEMORY.md.
"""


def _build_prompt(rows) -> str:
    lines = []
    for row in rows:
        ts = row.get("timestamp", "")
        source = row.get("source", "")
        content = row.get("content", "")
        lines.append(f"- [{ts}] ({source}) {content}")
    return DREAMS_PROMPT.format(memories="\n".join(lines) if lines else "(no new memories)")


def consolidate_memories(
    project: str = "default",
    memory_dir: Optional[Path] = None,
) -> int:
    try:
        if memory_dir:
            config_path = memory_dir / "config.yaml"
        else:
            config_path = None
        config = Config(config_path)
        db_path = config.database_path

        if not db_path.exists():
            print("Memory not initialized. Run 'memory init' first.", file=sys.stderr)
            return 1

        db = Database(db_path)
        db.connect()

        last_ts = db.get_state(f"last_consolidate_{project}")
        if last_ts:
            cursor = db.connect().execute(
                "SELECT id, timestamp, source, content FROM memories WHERE project = ? AND timestamp > ? ORDER BY timestamp ASC",
                (project, last_ts),
            )
            new_memories = [dict(row) for row in cursor.fetchall()]
        else:
            cursor = db.connect().execute(
                "SELECT id, timestamp, source, content FROM memories WHERE project = ? ORDER BY timestamp ASC LIMIT 200",
                (project,),
            )
            new_memories = [dict(row) for row in cursor.fetchall()]

        prompt = _build_prompt(new_memories)

        claude_path = shutil.which("claude")
        if not claude_path:
            print("Claude Code CLI not found.", file=sys.stderr)
            print("Install it or ensure `claude` is on PATH, then re-run.", file=sys.stderr)
            db.close()
            return 1

        print("Running Claude Code consolidation...")
        proc = subprocess.run(
            [claude_path, "-p", prompt],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            print(f"Claude Code failed: {proc.stderr}", file=sys.stderr)
            db.close()
            return 1

        print(proc.stdout)
        db.set_state(f"last_consolidate_{project}", datetime.utcnow().isoformat())
        db.close()
        return 0

    except Exception as e:
        print(f"Error consolidating memories: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Consolidate memories using Claude Code")
    parser.add_argument("--project", "-p", default="default", help="Project name")
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Memory directory path (default: ~/.memory)",
    )

    args = parser.parse_args()
    sys.exit(consolidate_memories(project=args.project, memory_dir=args.path))
