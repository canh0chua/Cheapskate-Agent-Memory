"""
memory status command - Show DB stats, last consolidate/prune times, config summary.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from cheapskate.config import Config
from cheapskate.db import Database


def memory_status(memory_dir: Optional[Path] = None) -> int:
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

        # Get basic stats
        stats = db.get_stats()

        print("=== Cheapskate Agent Memory Status ===\n")
        print(f"Database: {db_path}")
        print(f"Memory directory: {config.memory_dir}")
        print()

        # DB Statistics
        print("--- Database Statistics ---")
        print(f"Memories: {stats['memories']}")
        print(f"Topics: {stats['topics']}")
        print(f"Rules: {stats['rules']}")

        # Last consolidate time
        last_consolidate = db.get_state("last_consolidate_default")
        if last_consolidate:
            try:
                # Handle 'Z' suffix for UTC timezone
                ts_str = last_consolidate
                if ts_str.endswith("Z"):
                    ts_str = ts_str[:-1] + "+00:00"
                ts = datetime.fromisoformat(ts_str)
                ago = datetime.now(timezone.utc) - ts.replace(tzinfo=None)
                print(f"Last consolidate: {ts.strftime('%Y-%m-%d %H:%M:%S')} ({_format_timedelta(ago)})")
            except Exception:
                print(f"Last consolidate: {last_consolidate}")
        else:
            print("Last consolidate: never")

        # Last prune time
        last_prune = db.get_state("last_prune")
        if last_prune:
            try:
                # Handle 'Z' suffix for UTC timezone
                ts_str = last_prune
                if ts_str.endswith("Z"):
                    ts_str = ts_str[:-1] + "+00:00"
                ts = datetime.fromisoformat(ts_str)
                ago = datetime.now(timezone.utc) - ts.replace(tzinfo=None)
                print(f"Last prune: {ts.strftime('%Y-%m-%d %H:%M:%S')} ({_format_timedelta(ago)})")
            except Exception:
                print(f"Last prune: {last_prune}")
        else:
            print("Last prune: never")

        # Config summary
        print("\n--- Configuration Summary ---")
        print("Capture settings:")
        print(f"  auto_capture.ports: {config.get('capture.auto_capture.ports', True)}")
        print(f"  auto_capture.errors: {config.get('capture.auto_capture.errors', True)}")
        print(f"  auto_capture.commands: {config.get('capture.auto_capture.commands', True)}")
        print(f"  auto_capture.configs: {config.get('capture.auto_capture.configs', True)}")
        print(f"  auto_capture.conventions: {config.get('capture.auto_capture.conventions', True)}")
        print(f"  max_per_session: {config.get('capture.max_per_session', 50)}")
        tags_whitelist = config.get('capture.tags_whitelist', [])
        print(f"  tags_whitelist: {tags_whitelist if tags_whitelist else '(none)'}")

        print("\nConsolidation settings:")
        print(f"  schedule: {config.get('consolidate.schedule', '0 2 * * *')}")
        print(f"  trigger_threshold: {config.get('consolidate.trigger_threshold', 100)}")

        print("\nForgetting settings:")
        print(f"  decay_days: {config.get('forgetting.decay_days', 90)}")
        print(f"  max_age_days: {config.get('forgetting.max_age_days', 365)}")
        print(f"  include_contradicted: {config.get('forgetting.include_contradicted', False)}")
        print(f"  soft_delete: {config.get('forgetting.soft_delete', True)}")

        db.close()
        return 0

    except Exception as e:
        print(f"Error showing status: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def _format_timedelta(td):
    """Format timedelta into a human readable string."""
    total_seconds = int(td.total_seconds())
    if total_seconds < 60:
        return f"{total_seconds}s ago"
    elif total_seconds < 3600:
        minutes = total_seconds // 60
        return f"{minutes}m ago"
    elif total_seconds < 86400:
        hours = total_seconds // 3600
        return f"{hours}h ago"
    else:
        days = total_seconds // 86400
        return f"{days}d ago"


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Show memory system status")
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Memory directory path (default: ~/.memory)",
    )
    args = parser.parse_args()
    sys.exit(memory_status(memory_dir=args.path))
