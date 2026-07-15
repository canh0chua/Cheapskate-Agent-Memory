"""
memory status command - Show DB stats, last consolidate/prune times, config summary.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from cheapskate.config import Config
from cheapskate.db import Database


def memory_status(memory_dir: Optional[Path] = None, json_output: bool = False) -> int:
    try:
        if memory_dir:
            config_path = memory_dir / "config.yaml"
        else:
            config_path = None
        config = Config(config_path)
        db_path = config.database_path

        if not db_path.exists():
            if json_output:
                output = {
                    "initialized": False,
                    "memory_dir": str(config.memory_dir),
                    "database_path": str(db_path),
                    "stats": {},
                    "last_consolidate": None,
                    "last_prune": None,
                }
                print(json.dumps(output, indent=2))
            else:
                print("Memory not initialized. Run 'memory init' first.", file=sys.stderr)
            return 1

        db = Database(db_path)
        db.connect()

        # Get basic stats
        stats = db.get_stats()

        # Last consolidate time
        last_consolidate = db.get_state("last_consolidate_default")
        last_consolidate_formatted = None
        if last_consolidate:
            try:
                ts_str = last_consolidate
                if ts_str.endswith("Z"):
                    ts_str = ts_str[:-1] + "+00:00"
                ts = datetime.fromisoformat(ts_str)
                last_consolidate_formatted = ts.isoformat()
            except Exception:
                last_consolidate_formatted = last_consolidate

        # Last prune time
        last_prune = db.get_state("last_prune")
        last_prune_formatted = None
        if last_prune:
            try:
                ts_str = last_prune
                if ts_str.endswith("Z"):
                    ts_str = ts_str[:-1] + "+00:00"
                ts = datetime.fromisoformat(ts_str)
                last_prune_formatted = ts.isoformat()
            except Exception:
                last_prune_formatted = last_prune

        if json_output:
            output = {
                "initialized": True,
                "memory_dir": str(config.memory_dir),
                "database_path": str(db_path),
                "stats": {
                    "memories": stats['memories'],
                    "topics": stats['topics'],
                    "rules": stats['rules'],
                },
                "last_consolidate": last_consolidate_formatted,
                "last_prune": last_prune_formatted,
                "config_summary": {
                    "capture_settings": {
                        "auto_capture_ports": config.get('capture.auto_capture.ports', True),
                        "auto_capture_errors": config.get('capture.auto_capture.errors', True),
                        "auto_capture_commands": config.get('capture.auto_capture.commands', True),
                        "auto_capture_configs": config.get('capture.auto_capture.configs', True),
                        "auto_capture_conventions": config.get('capture.auto_capture.conventions', True),
                        "max_per_session": config.get('capture.max_per_session', 50),
                        "tags_whitelist": config.get('capture.tags_whitelist', []),
                    },
                    "consolidation_settings": {
                        "schedule": config.get('consolidate.schedule', '0 2 * * *'),
                        "trigger_threshold": config.get('consolidate.trigger_threshold', 100),
                    },
                    "forgetting_settings": {
                        "decay_days": config.get('forgetting.decay_days', 90),
                        "max_age_days": config.get('forgetting.max_age_days', 365),
                        "include_contradicted": config.get('forgetting.include_contradicted', False),
                        "soft_delete": config.get('forgetting.soft_delete', True),
                    },
                },
            }
            print(json.dumps(output, indent=2))
        else:
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
            if last_consolidate:
                try:
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
            if last_prune:
                try:
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
