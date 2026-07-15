"""
Cheapskate Agent Memory CLI.

A zero-cost, zero-dependency, fully-local memory system for coding agents.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from cheapskate.commands.add import add_memory
from cheapskate.commands.init import init_memory
from cheapskate.commands.list import list_memories
from cheapskate.commands.search import search_memories


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        prog="memory",
        description="Cheapskate Agent Memory - Zero-cost, fully-local memory for coding agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  memory init                                    Initialize the memory database
  memory add "Port 4000 is the dev server"       Add a memory
  memory add "Using pnpm for this project" -p myapp -t node  Add with project and tags
  memory list                                    List all memories
  memory list -p myapp                           List memories for a project
  memory search "port"                           Search memories
  memory search "docker" -p myapp -n 10         Search with project and limit
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize memory database")
    init_parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Memory directory path (default: ~/.memory)",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Force reinitialization",
    )

    # Add command
    add_parser = subparsers.add_parser("add", help="Add a memory entry")
    add_parser.add_argument("content", help="Memory content to store")
    add_parser.add_argument(
        "--project",
        "-p",
        default=None,
        help="Project name (default: default)",
    )
    add_parser.add_argument(
        "--tags",
        "-t",
        help="Comma-separated tags",
    )
    add_parser.add_argument(
        "--source",
        "-s",
        choices=["user", "agent", "extracted", "llm_consolidate"],
        default="agent",
        help="Memory source (default: agent)",
    )
    add_parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Memory directory path (default: ~/.memory)",
    )

    # List command
    list_parser = subparsers.add_parser("list", help="List memory entries")
    list_parser.add_argument(
        "--project",
        "-p",
        default=None,
        help="Filter by project name",
    )
    list_parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=100,
        help="Maximum number of entries (default: 100)",
    )
    list_parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Memory directory path (default: ~/.memory)",
    )

    # Search command
    search_parser = subparsers.add_parser("search", help="Search memory entries")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument(
        "--project",
        "-p",
        default=None,
        help="Filter by project name",
    )
    search_parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=20,
        help="Maximum number of results (default: 20)",
    )
    search_parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Output as JSON",
    )
    search_parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Memory directory path (default: ~/.memory)",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    # Execute command
    try:
        if args.command == "init":
            return init_memory(memory_dir=args.path, force=args.force)
        elif args.command == "add":
            tags = None
            if args.tags:
                tags = [t.strip() for t in args.tags.split(",")]
            return add_memory(
                content=args.content,
                project=args.project,
                tags=tags,
                source=args.source,
                memory_dir=args.path,
            )
        elif args.command == "list":
            return list_memories(
                project=args.project,
                limit=args.limit,
                memory_dir=args.path,
            )
        elif args.command == "search":
            return search_memories(
                query=args.query,
                project=args.project,
                limit=args.limit,
                json_output=args.json,
                memory_dir=args.path,
            )
        else:
            parser.print_help()
            return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())