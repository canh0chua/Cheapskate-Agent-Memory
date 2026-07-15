"""
memory topic command - List, create, and delete topics.

Manages topic files and database entries for memory organization.
"""

import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from cheapskate.config import Config
from cheapskate.db import Database
from cheapskate.commands.topicify import (
    get_claude_memory_dir,
    get_topics_dir,
    extract_keywords,
    generate_topic_summary,
    write_topic_file,
)


def list_topics(
    project: Optional[str] = None,
    memory_dir: Optional[Path] = None,
) -> int:
    """
    List existing topics.

    Args:
        project: Filter by project name
        memory_dir: Path to memory directory

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

        # Get topics
        topics = db.get_topics(project=project)

        if not topics:
            print("No topics found.")
            if project:
                print(f"(Project: {project})")
            return 0

        # Display topics
        print(f"Found {len(topics)} topic(s):")
        print("-" * 60)

        for topic in topics:
            print(f"\n[{topic['id']}] {topic['name']}")
            print(f"  Project: {topic['project']}")
            if topic.get("summary"):
                summary = topic["summary"]
                if len(summary) > 100:
                    summary = summary[:100] + "..."
                print(f"  Summary: {summary}")
            if topic.get("memory_ids"):
                print(f"  Memories: {len(topic['memory_ids'])} linked")
            if topic.get("last_updated"):
                updated = datetime.fromisoformat(topic["last_updated"]).strftime("%Y-%m-%d %H:%M")
                print(f"  Updated: {updated}")

        print("-" * 60)
        db.close()
        return 0

    except Exception as e:
        print(f"Error listing topics: {e}", file=sys.stderr)
        return 1


def create_topic(
    name: str,
    project: str,
    memory_ids: Optional[List[int]] = None,
    memory_dir: Optional[Path] = None,
) -> int:
    """
    Create a new topic manually.

    Args:
        name: Topic name
        project: Project name
        memory_ids: Optional list of memory IDs to link
        memory_dir: Path to memory directory

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

        # Check if topic already exists
        existing = db.get_topic(project, name)
        if existing:
            print(f"Topic '{name}' already exists for project '{project}'.", file=sys.stderr)
            print(f"Use 'memory topic update' or 'memory topicify' to modify it.")
            db.close()
            return 1

        # Get linked memories if IDs provided
        memories = []
        if memory_ids:
            for mid in memory_ids:
                mem = db.get_memory(mid)
                if mem:
                    memories.append(mem)
                else:
                    print(f"Warning: Memory #{mid} not found, skipping.", file=sys.stderr)

        # Generate summary from linked memories
        if memories:
            summary = generate_topic_summary(memories, name)
        else:
            summary = f"# {name.title()}\n\n_Empty topic - add memories with topicify_"

        # Insert into database
        topic_id = db.upsert_topic(project, name, summary, memory_ids or [])

        # Write topic file
        filepath = write_topic_file(project, name, summary, memory_ids or [])

        print(f"Created topic '{name}' (ID: {topic_id})")
        print(f"  Project: {project}")
        print(f"  Memories: {len(memories) if memories else 0} linked")
        print(f"  File: {filepath}")

        db.close()
        return 0

    except Exception as e:
        print(f"Error creating topic: {e}", file=sys.stderr)
        return 1


def delete_topic(
    name: str,
    project: str,
    memory_dir: Optional[Path] = None,
    force: bool = False,
) -> int:
    """
    Delete a topic.

    Args:
        name: Topic name
        project: Project name
        memory_dir: Path to memory directory
        force: Skip confirmation prompt

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

        # Check if topic exists
        topic = db.get_topic(project, name)
        if not topic:
            print(f"Topic '{name}' not found for project '{project}'.", file=sys.stderr)
            db.close()
            return 1

        # Confirmation
        if not force:
            response = input(f"Delete topic '{name}' (project: {project})? [y/N] ")
            if response.lower() != "y":
                print("Cancelled.")
                db.close()
                return 0

        # Delete from database
        db.delete_topic(project, name)

        # Delete topic file
        topics_dir = get_topics_dir(project)
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "-", name.lower())
        filepath = topics_dir / f"{safe_name}.md"

        if filepath.exists():
            filepath.unlink()
            print(f"Deleted topic file: {filepath}")

        print(f"Deleted topic '{name}' from database and filesystem.")

        db.close()
        return 0

    except Exception as e:
        print(f"Error deleting topic: {e}", file=sys.stderr)
        return 1


def manage_topics(
    action: str,
    name: Optional[str] = None,
    project: Optional[str] = None,
    memory_ids: Optional[List[int]] = None,
    memory_dir: Optional[Path] = None,
    force: bool = False,
) -> int:
    """
    Main entry point for topic management.

    Args:
        action: 'list', 'create', or 'delete'
        name: Topic name (for create/delete)
        project: Project name
        memory_ids: Memory IDs to link (for create)
        memory_dir: Path to memory directory
        force: Skip confirmation (for delete)

    Returns:
        Exit code
    """
    project = project or "default"

    if action == "list":
        return list_topics(project=project, memory_dir=memory_dir)
    elif action == "create":
        if not name:
            print("Error: --name is required for create", file=sys.stderr)
            return 1
        return create_topic(
            name=name,
            project=project,
            memory_ids=memory_ids,
            memory_dir=memory_dir,
        )
    elif action == "delete":
        if not name:
            print("Error: --name is required for delete", file=sys.stderr)
            return 1
        return delete_topic(
            name=name,
            project=project,
            memory_dir=memory_dir,
            force=force,
        )
    else:
        print(f"Unknown action: {action}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Manage memory topics")
    subparsers = parser.add_subparsers(dest="action", help="Topic action")

    # List subcommand
    list_parser = subparsers.add_parser("list", help="List topics")
    list_parser.add_argument(
        "--project", "-p",
        default=None,
        help="Filter by project name",
    )
    list_parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Memory directory path (default: ~/.memory)",
    )

    # Create subcommand
    create_parser = subparsers.add_parser("create", help="Create a topic")
    create_parser.add_argument("name", help="Topic name")
    create_parser.add_argument(
        "--project", "-p",
        default=None,
        help="Project name (default: default)",
    )
    create_parser.add_argument(
        "--memory-ids", "-m",
        help="Comma-separated memory IDs to link",
    )
    create_parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Memory directory path (default: ~/.memory)",
    )

    # Delete subcommand
    delete_parser = subparsers.add_parser("delete", help="Delete a topic")
    delete_parser.add_argument("name", help="Topic name")
    delete_parser.add_argument(
        "--project", "-p",
        default=None,
        help="Project name (default: default)",
    )
    delete_parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Memory directory path (default: ~/.memory)",
    )
    delete_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Skip confirmation",
    )

    args = parser.parse_args()

    memory_ids = None
    if hasattr(args, "memory_ids") and args.memory_ids:
        memory_ids = [int(x.strip()) for x in args.memory_ids.split(",")]

    project = getattr(args, "project", None)

    if args.action == "list":
        sys.exit(list_topics(project=args.project, memory_dir=args.path))
    elif args.action == "create":
        sys.exit(create_topic(
            name=args.name,
            project=project or "default",
            memory_ids=memory_ids,
            memory_dir=args.path,
        ))
    elif args.action == "delete":
        sys.exit(delete_topic(
            name=args.name,
            project=project or "default",
            memory_dir=args.path,
            force=args.force,
        ))
    else:
        parser.print_help()
        sys.exit(1)