"""
memory search command - Full-text search on memory entries.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from cheapskate.config import Config
from cheapskate.db import Database


def search_memories(
    query: str,
    project: Optional[str] = None,
    all_projects: bool = False,
    limit: int = 20,
    json_output: bool = False,
    memory_dir: Optional[Path] = None,
) -> int:
    """
    Search memory entries using full-text search.

    Args:
        query: Search query string
        project: Filter by project name
        limit: Maximum number of results
        json_output: Output as JSON
        memory_dir: Path to memory directory

    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        if not query or not query.strip():
            print("Error: Query is required", file=sys.stderr)
            return 1

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

        # Search memories
        # Determine project filter: --all-projects overrides --project
        filter_project = None if all_projects else project
        results = db.search_memories(query=query, project=filter_project, limit=limit)

        if not results:
            print("No results found.")
            if project:
                print(f"(Project: {project})")
            print(f"(Query: {query})")
            return 0

        if json_output:
            # Output as JSON
            output = {
                "query": query,
                "count": len(results),
                "results": [
                    {
                        "id": r["id"],
                        "project": r["project"],
                        "timestamp": r["timestamp"],
                        "source": r["source"],
                        "content": r["content"],
                        "rank": r.get("rank"),
                    }
                    for r in results
                ],
            }
            print(json.dumps(output, indent=2))
        else:
            # Human-readable output
            print(f"Found {len(results)} result(s):")
            print("-" * 60)

            for r in results:
                timestamp = datetime.fromisoformat(r["timestamp"]).strftime("%Y-%m-%d %H:%M")
                print(f"\n[{r['id']}] {timestamp}")
                print(f"  Project: {r['project']}")
                print(f"  Source: {r['source']}")
                print(f"  {r['content']}")
                abstract = r.get("abstract")
                if abstract:
                    print(f"  Abstract: {abstract}")

            print("-" * 60)

        db.close()
        return 0

    except Exception as e:
        print(f"Error searching memories: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Search memory entries")
    parser.add_argument("query", help="Search query")
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
        default=20,
        help="Maximum number of results (default: 20)",
    )
    parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Output as JSON",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Memory directory path (default: ~/.memory)",
    )

    args = parser.parse_args()

    sys.exit(search_memories(
        query=args.query,
        project=args.project,
        limit=args.limit,
        json_output=args.json,
        memory_dir=args.path,
    ))