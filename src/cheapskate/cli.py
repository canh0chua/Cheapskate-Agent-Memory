"""
Cheapskate Agent Memory CLI.

A zero-cost, zero-dependency, fully-local memory system for coding agents.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from cheapskate.commands.add import add_memory
from cheapskate.commands.audit import audit_memories
from cheapskate.commands.consolidate import consolidate_memories
from cheapskate.commands.init import init_memory
from cheapskate.commands.list import list_memories
from cheapskate.commands.prune import prune_memories
from cheapskate.commands.search import search_memories
from cheapskate.commands.topicify import topicify_memories
from cheapskate.commands.topics import manage_topics
from cheapskate.memory_md import generate_memory_md


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
  memory topicify -p myapp                       Auto-group memories into topics
  memory topicify -p myapp --group-by tags       Group by tags only
  memory topic list                              List existing topics
  memory topic create debugging -p myapp -m 1,2  Create topic with linked memories
  memory topic delete old-topic -p myapp          Delete a topic
  memory memory-md -p myapp                      Generate MEMORY.md index
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

    # Topicify command
    topicify_parser = subparsers.add_parser("topicify", help="Auto-group memories into topics")
    topicify_parser.add_argument(
        "--project",
        "-p",
        default=None,
        help="Project name (default: default)",
    )
    topicify_parser.add_argument(
        "--threshold",
        "-t",
        type=float,
        default=0.3,
        help="Similarity threshold (0.0 to 1.0, default: 0.3)",
    )
    topicify_parser.add_argument(
        "--group-by",
        "-g",
        choices=["auto", "tags", "vector", "keywords"],
        default="auto",
        help="Grouping strategy (default: auto)",
    )
    topicify_parser.add_argument(
        "--auto",
        "-a",
        action="store_true",
        help="Auto-create topics without prompting",
    )
    topicify_parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Memory directory path (default: ~/.memory)",
    )

    # Topic subcommand (list/create/delete)
    topic_parser = subparsers.add_parser("topic", help="Manage topics")
    topic_subparsers = topic_parser.add_subparsers(dest="topic_action", help="Topic action")

    # Topic list
    topic_list_parser = topic_subparsers.add_parser("list", help="List topics")
    topic_list_parser.add_argument(
        "--project",
        "-p",
        default=None,
        help="Filter by project name",
    )
    topic_list_parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Memory directory path (default: ~/.memory)",
    )

    # Topic create
    topic_create_parser = topic_subparsers.add_parser("create", help="Create a topic")
    topic_create_parser.add_argument("name", help="Topic name")
    topic_create_parser.add_argument(
        "--project",
        "-p",
        default=None,
        help="Project name (default: default)",
    )
    topic_create_parser.add_argument(
        "--memory-ids",
        "-m",
        help="Comma-separated memory IDs to link",
    )
    topic_create_parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Memory directory path (default: ~/.memory)",
    )

    # Topic delete
    topic_delete_parser = topic_subparsers.add_parser("delete", help="Delete a topic")
    topic_delete_parser.add_argument("name", help="Topic name")
    topic_delete_parser.add_argument(
        "--project",
        "-p",
        default=None,
        help="Project name (default: default)",
    )
    topic_delete_parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Memory directory path (default: ~/.memory)",
    )
    topic_delete_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Skip confirmation",
    )

    # Memory-md command (generate MEMORY.md)
    memory_md_parser = subparsers.add_parser("memory-md", help="Generate MEMORY.md index")
    memory_md_parser.add_argument(
        "--project",
        "-p",
        default=None,
        help="Project name (default: default)",
    )
    memory_md_parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Memory directory path (default: ~/.memory)",
    )
    memory_md_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Overwrite existing file",
    )

    # Prune command
    prune_parser = subparsers.add_parser("prune", help="Prune old memories")
    prune_parser.add_argument(
        "--project",
        "-p",
        default=None,
        help="Project name (default: default)",
    )
    prune_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be pruned without deleting",
    )
    prune_parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Memory directory path (default: ~/.memory)",
    )

    # Audit command
    audit_parser = subparsers.add_parser("audit", help="Show recent memory changes")
    audit_parser.add_argument(
        "--project",
        "-p",
        default=None,
        help="Project name (default: default)",
    )
    audit_parser.add_argument(
        "--action",
        "-a",
        default=None,
        choices=["add", "update", "prune", "contradict", "access"],
        help="Filter by action type",
    )
    audit_parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=50,
        help="Max entries (default: 50)",
    )
    audit_parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Memory directory path (default: ~/.memory)",
    )

    # Consolidate command
    consolidate_parser = subparsers.add_parser("consolidate", help="Consolidate memories via Claude Code")
    consolidate_parser.add_argument(
        "--project",
        "-p",
        default="default",
        help="Project name (default: default)",
    )
    consolidate_parser.add_argument(
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

        elif args.command == "topicify":
            project = args.project or "default"
            return topicify_memories(
                project=project,
                memory_dir=args.path,
                threshold=args.threshold,
                group_by=args.group_by,
                auto=args.auto,
            )

        elif args.command == "topic":
            # Handle topic subcommands
            memory_ids = None
            if hasattr(args, "memory_ids") and args.memory_ids:
                memory_ids = [int(x.strip()) for x in args.memory_ids.split(",")]

            project = getattr(args, "project", None) or "default"

            if args.topic_action == "list":
                return manage_topics(
                    action="list",
                    project=args.project,
                    memory_dir=args.path,
                )
            elif args.topic_action == "create":
                return manage_topics(
                    action="create",
                    name=args.name,
                    project=project,
                    memory_ids=memory_ids,
                    memory_dir=args.path,
                )
            elif args.topic_action == "delete":
                return manage_topics(
                    action="delete",
                    name=args.name,
                    project=project,
                    memory_dir=args.path,
                    force=args.force,
                )
            else:
                topic_parser.print_help()
                return 1

        elif args.command == "prune":
            project = getattr(args, "project", None)
            return prune_memories(
                project=project,
                dry_run=args.dry_run,
                memory_dir=args.path,
            )

        elif args.command == "audit":
            return audit_memories(
                project=args.project,
                limit=args.limit,
                action=args.action,
                memory_dir=args.path,
            )

        elif args.command == "consolidate":
            return consolidate_memories(
                project=args.project,
                memory_dir=args.path,
            )

        elif args.command == "memory-md":
            project = args.project or "default"
            return generate_memory_md(
                project=project,
                memory_dir=args.path,
                force=args.force,
            )

        else:
            parser.print_help()
            return 1

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())