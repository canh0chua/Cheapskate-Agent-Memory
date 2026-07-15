"""
memory audit command - Show recent memory changes from audit table.
"""

import sys
from pathlib import Path
from typing import Optional

from cheapskate.config import Config, default_memory_dir
from cheapskate.db import Database


def audit_memories(
    project: Optional[str] = None,
    limit: int = 50,
    action: Optional[str] = None,
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

        rows = db.get_audit_trail(project=project, action=action, limit=limit)
        if not rows:
            print("No audit entries found.")
            db.close()
            return 0

        print(f"{'ID':<6} {'Action':<12} {'Reason':<18} {'Agent':<12} {'Time'}")
        print("-" * 80)
        for row in rows:
            memory_id = row.get("memory_id") or ""
            action_text = row.get("action") or ""
            reason = row.get("reason") or ""
            agent = row.get("agent_id") or ""
            ts = row.get("timestamp") or ""
            print(f"{str(memory_id):<6} {action_text:<12} {reason:<18} {agent:<12} {ts}")

        db.close()
        return 0

    except Exception as e:
        print(f"Error reading audit trail: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Show recent memory changes")
    parser.add_argument("--project", "-p", default=None, help="Project name")
    parser.add_argument(
        "--action",
        "-a",
        default=None,
        choices=["add", "update", "prune", "contradict", "access"],
        help="Filter by action type",
    )
    parser.add_argument("--limit", "-n", type=int, default=50, help="Max entries (default: 50)")
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Memory directory path (default: ~/.memory)",
    )

    args = parser.parse_args()
    sys.exit(
        audit_memories(
            project=args.project,
            limit=args.limit,
            action=args.action,
            memory_dir=args.path,
        )
    )
