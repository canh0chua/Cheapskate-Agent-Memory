"""
memory prune command - Apply forgetting config: decay_days, max_age_days.
"""

import json
import sys
from pathlib import Path
from typing import Optional

from cheapskate.config import Config, default_memory_dir
from cheapskate.db import Database


def prune_memories(
    project: Optional[str] = None,
    dry_run: bool = False,
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

        decay_days = int(config.get("forgetting.decay_days", 90) or 90)
        max_age_days = int(config.get("forgetting.max_age_days", 365) or 365)
        soft_delete = bool(config.get("forgetting.soft_delete", True))
        agent_id = "cli"

        result = db.prune_memories(
            project=project,
            decay_days=decay_days,
            max_age_days=max_age_days,
            soft_delete=soft_delete,
            dry_run=dry_run,
            agent_id=agent_id,
        )

        if dry_run:
            print("DRY RUN")
            print(f"Would prune {result.get('would_prune_count', 0)} memories")
            ids = result.get("memory_ids", [])
            if ids:
                print(f"Memory IDs: {ids}")
        else:
            print(f"Pruned {result.get('pruned_count', 0)} memories")
            ids = result.get("memory_ids", [])
            if ids:
                print(f"Memory IDs: {ids}")
            print(f"dry_run=false")

        db.close()
        return 0

    except Exception as e:
        print(f"Error pruning memories: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Prune old memories")
    parser.add_argument("--project", "-p", default=None, help="Project name")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be pruned without deleting",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Memory directory path (default: ~/.memory)",
    )

    args = parser.parse_args()
    sys.exit(prune_memories(project=args.project, dry_run=args.dry_run, memory_dir=args.path))
