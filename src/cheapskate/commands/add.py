"""
memory add command - Add a new memory entry.
"""

import re
import sys
from pathlib import Path
from typing import List, Optional

from cheapskate.config import Config, validate_memory_path
from cheapskate.db import Database
from cheapskate.hrr import encode, pack_vector


# Input validation limits
MAX_CONTENT_LENGTH = 10_000  # 10KB per memory
MAX_PROJECT_LENGTH = 255
MAX_TAG_LENGTH = 50
MAX_TAGS_PER_MEMORY = 20
VALID_PROJECT_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')


def validate_input(
    content: str,
    project: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Optional[str]:
    """
    Validate memory input parameters.

    Args:
        content: The memory content to validate
        project: Optional project name to validate
        tags: Optional list of tags to validate

    Returns:
        Error message if validation fails, None if valid
    """
    # Validate content length
    if len(content) > MAX_CONTENT_LENGTH:
        return f"Content exceeds maximum length of {MAX_CONTENT_LENGTH} characters"

    # Validate project name
    if project is not None:
        if len(project) > MAX_PROJECT_LENGTH:
            return f"Project name exceeds maximum length of {MAX_PROJECT_LENGTH} characters"
        if not VALID_PROJECT_PATTERN.match(project):
            return "Project name must contain only alphanumeric characters, dashes, and underscores"

    # Validate tags
    if tags:
        if len(tags) > MAX_TAGS_PER_MEMORY:
            return f"Too many tags (max {MAX_TAGS_PER_MEMORY})"

        for tag in tags:
            if len(tag) > MAX_TAG_LENGTH:
                return f"Tag '{tag[:20]}...' exceeds maximum length of {MAX_TAG_LENGTH} characters"
            if not VALID_PROJECT_PATTERN.match(tag):
                return f"Tag '{tag}' contains invalid characters (alphanumeric, dash, underscore only)"

    return None


def add_memory(
    content: str,
    project: Optional[str] = None,
    tags: Optional[List[str]] = None,
    source: str = "agent",
    memory_dir: Optional[Path] = None,
) -> int:
    """
    Add a new memory entry.

    Args:
        content: The memory content/text to store
        project: Project name (defaults to 'default')
        tags: Optional list of tags
        source: Source of the memory (user, agent, extracted, llm_consolidate)
        memory_dir: Path to memory directory

    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        # Use default project if not specified
        if not project:
            project = "default"

        # Validate input
        error = validate_input(content, project, tags)
        if error:
            print(f"Error: {error}", file=sys.stderr)
            return 1

        # Validate memory directory path
        validated_dir = validate_memory_path(memory_dir, force=False)

        # Load config and get database path
        config_path = validated_dir / "config.yaml"
        config = Config(config_path)
        db_path = config.database_path

        # Check if database exists
        if not db_path.exists():
            print(f"Memory not initialized. Run 'memory init' first.", file=sys.stderr)
            return 1

        # Connect to database
        db = Database(db_path)
        db.connect()

        # Encode content to HRR vector
        embedding = pack_vector(encode(content))

        # Add memory
        memory_id = db.add_memory(
            project=project,
            content=content,
            source=source,
            embedding=embedding,
            tags=tags,
        )

        print(f"Added memory #{memory_id}")
        print(f"  Project: {project}")
        print(f"  Source: {source}")
        if tags:
            print(f"  Tags: {', '.join(tags)}")

        db.close()
        return 0

    except Exception as e:
        print(f"Error adding memory: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Add a memory entry")
    parser.add_argument("content", help="Memory content to store")
    parser.add_argument(
        "--project",
        "-p",
        default=None,
        help="Project name (default: default)",
    )
    parser.add_argument(
        "--tags",
        "-t",
        help="Comma-separated tags",
    )
    parser.add_argument(
        "--source",
        "-s",
        choices=["user", "agent", "extracted", "llm_consolidate"],
        default="agent",
        help="Memory source (default: agent)",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Memory directory path (default: ~/.memory)",
    )

    args = parser.parse_args()
    tags = None
    if args.tags:
        tags = [t.strip() for t in args.tags.split(",")]

    sys.exit(add_memory(
        args.content,
        project=args.project,
        tags=tags,
        source=args.source,
        memory_dir=args.path,
    ))