"""
memory init command - Initialize the memory database and config.
"""

import sys
from pathlib import Path
from typing import Optional

from cheapskate.config import DEFAULT_CONFIG, Config, validate_memory_path
from cheapskate.db import init_database


def init_memory(memory_dir: Optional[Path] = None, force: bool = False) -> int:
    """
    Initialize the memory database and config.

    Args:
        memory_dir: Path to memory directory (default: ~/.memory)
        force: If True, reinitialize even if already exists

    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        # Validate memory directory path (prevent traversal unless forced)
        memory_path = validate_memory_path(memory_dir, force=force)
        memory_path.mkdir(parents=True, exist_ok=True)
        config_path = memory_path / "config.yaml"
        db_path = memory_path / "memory.db"

        # Check if already initialized
        if db_path.exists() and not force:
            print(f"Memory already initialized at {memory_path}")
            print("Use --force to reinitialize")
            return 1

        # Write default config
        if not config_path.exists() or force:
            config_path.write_text(DEFAULT_CONFIG + "\n", encoding="utf-8")
            print(f"Created config: {config_path}")

        # Initialize database
        db = init_database(db_path)
        db.init_schema()
        print(f"Initialized database: {db_path}")

        # Get stats
        stats = db.get_stats()
        print(f"Database ready: {stats['memories']} memories, {stats['topics']} topics, {stats['rules']} rules")

        db.close()
        return 0

    except Exception as e:
        print(f"Error initializing memory: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Initialize memory database")
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Memory directory path (default: ~/.memory)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reinitialization",
    )

    args = parser.parse_args()
    sys.exit(init_memory(args.path, args.force))