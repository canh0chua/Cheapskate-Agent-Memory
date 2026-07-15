"""
memory list command - List memory entries.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from cheapskate.config import Config
from cheapskate.db import Database


def list_memories(
    project: Optional[str] = None,
    all_projects: bool = False,
    limit: int = 100,
    memory_dir: Optional[Path] = None,
    json_output: bool = False,
) -> int:
    """
    List memory entries.

    Args:
        project: Filter by project name
        limit: Maximum number of entries to return
        memory_dir: Path to memory directory
        json_output: Output results as JSON

    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        # Load config and get database path
        if memory_dir:
            config_path = memory_dir / "config.yaml"
        else:
            config_path = None
        config = Config(config_path)
        db_path = config.database_path

        # Check if database exists
        if not db_path.exists():
            print(f"Memory not initialized. Run 'memory init' first.", file=sys.stderr)
            return 1

        # Connect to database
        db = Database(db_path)
        db.connect()

        # Determine project filter: --all-projects overrides --project
        filter_project = None if all_projects else project

        # Get memories
        memories = db.list_memories(project=filter_project, limit=limit)

        if not memories:
            if json_output:
                output = {
                    "memories": [],
                    "count": 0,
                    "project": project if not all_projects else None,
                    "all_projects": all_projects,
                }
                print(json.dumps(output, indent=2))
            else:
                print("No memories found.")
                if project:
                    print(f"(Project: {project})")
            return 0

        if json_output:
            # Output as JSON
            output = {
                "memories": [
                    {
                        "id": mem["id"],
                        "project": mem["project"],
                        "timestamp": mem["timestamp"],
                        "source": mem["source"],
                        "content": mem["content"],
                        "abstract": mem.get("abstract"),
                        "accessed_at": mem.get("accessed_at"),
                    }
                    for mem in memories
                ],
                "count": len(memories),
                "project": project if not all_projects else None,
                "all_projects": all_projects,
            }
            print(json.dumps(output, indent=2))
        else:
            # Display memories
            print(f"Found {len(memories)} memory/ies:")
            print("-" * 60)

            for mem in memories:
                timestamp = datetime.fromisoformat(mem["timestamp"]).strftime("%Y-%m-%d %H:%M")
                print(f"\n[{mem['id']}] {timestamp}")
                if all_projects or project is None:
                    print(f"  Project: {mem['project']}")
                print(f"  Source: {mem['source']}")
                content = mem["content"]
                if len(content) > 200:
                    content = content[:200] + "..."
                print(f"  Content: {content}")
                abstract = mem.get("abstract")
                if abstract:
                    print(f"  Abstract: {abstract}")

            print("-" * 60)

            # Show stats
            stats = db.get_stats()
            print(f"\nTotal in database: {stats['memories']} memories, {stats['topics']} topics, {stats['rules']} rules")

        db.close()
        return 0

    except Exception as e:
        print(f"Error listing memories: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="List memory entries")
    parser.add_argument(
        "--project",
        "-p",
        default=None,
        help="Filter by project name",
    )
    parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=100,
        help="Maximum number of entries (default: 100)",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Memory directory path (default: ~/.memory)",
    )

    args = parser.parse_args()

    sys.exit(list_memories(
        project=args.project,
        limit=args.limit,
        memory_dir=args.path,
    ))