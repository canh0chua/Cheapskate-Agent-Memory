"""
memory stats command - Show statistics: counts per project/source/tag, age distribution.
"""
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from cheapskate.config import Config
from cheapskate.db import Database


def memory_stats(memory_dir: Optional[Path] = None, project: Optional[str] = None) -> int:
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

        # Fetch memories, optionally filtered by project
        if project:
            cursor = db.connect().execute(
                "SELECT project, source, timestamp, metadata FROM memories WHERE project = ? ORDER BY timestamp DESC",
                (project,),
            )
        else:
            cursor = db.connect().execute(
                "SELECT project, source, timestamp, metadata FROM memories ORDER BY timestamp DESC"
            )
        rows = cursor.fetchall()

        if not rows:
            print("No memories found in database.")
            db.close()
            return 0

        # Aggregations
        project_counts = Counter()
        source_counts = Counter()
        tag_counts = Counter()
        age_buckets = {
            "Today": 0,
            "Last 7 days": 0,
            "Last 30 days": 0,
            "Last 90 days": 0,
            "Older": 0,
        }

        now = datetime.now(timezone.utc)
        today_cutoff = now - timedelta(days=1)
        week_cutoff = now - timedelta(days=7)
        month_cutoff = now - timedelta(days=30)
        quarter_cutoff = now - timedelta(days=90)

        for row in rows:
            project = row["project"] or "(no project)"
            source = row["source"] or "(no source)"
            timestamp_str = row["timestamp"]
            metadata_str = row["metadata"]

            project_counts[project] += 1
            source_counts[source] += 1

            # Parse timestamp for age buckets
            try:
                ts = datetime.fromisoformat(timestamp_str)
                if ts >= today_cutoff:
                    age_buckets["Today"] += 1
                elif ts >= week_cutoff:
                    age_buckets["Last 7 days"] += 1
                elif ts >= month_cutoff:
                    age_buckets["Last 30 days"] += 1
                elif ts >= quarter_cutoff:
                    age_buckets["Last 90 days"] += 1
                else:
                    age_buckets["Older"] += 1
            except Exception:
                age_buckets["Older"] += 1  # fallback for bad timestamps

            # Parse tags from metadata
            if metadata_str:
                try:
                    metadata = json.loads(metadata_str)
                    tags = metadata.get("tags", [])
                    if isinstance(tags, list):
                        for tag in tags:
                            tag_counts[str(tag)] += 1
                except Exception:
                    pass

        # Display results
        print("=== Cheapskate Agent Memory Statistics ===\n")
        print(f"Total memories: {len(rows)}\n")

        print("--- By Project ---")
        for project, count in project_counts.most_common():
            print(f"  {project}: {count}")

        print("\n--- By Source ---")
        for source, count in source_counts.most_common():
            print(f"  {source}: {count}")

        print("\n--- By Tag ---")
        if tag_counts:
            for tag, count in tag_counts.most_common():
                print(f"  {tag}: {count}")
        else:
            print("  (no tags found)")

        print("\n--- Age Distribution ---")
        for bucket, count in age_buckets.items():
            print(f"  {bucket}: {count}")

        db.close()
        return 0

    except Exception as e:
        print(f"Error generating statistics: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Show memory statistics")
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Memory directory path (default: ~/.memory)",
    )
    parser.add_argument(
        "--project",
        "-p",
        default=None,
        help="Filter by project name",
    )
    args = parser.parse_args()
    sys.exit(memory_stats(memory_dir=args.path, project=args.project))
