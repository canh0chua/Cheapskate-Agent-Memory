"""
memory suggest command — proactively suggest relevant memories from current project.
"""

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from cheapskate.config import Config, validate_memory_path
from cheapskate.db import Database


def detect_project() -> Optional[str]:
    """
    Auto-detect project name from current working directory.

    Checks: .git/config, package.json, pyproject.toml, folder name
    """
    cwd = Path.cwd()

    # Check .git/config for repo name
    git_config = cwd / ".git" / "config"
    if git_config.exists():
        try:
            content = git_config.read_text()
            match = re.search(r'\[\s*remote\s+"origin"\s*\]\s*url\s*=\s*.*[/]([^/]+?)(?:\.git)?$', content, re.MULTILINE)
            if match:
                return match.group(1)
        except Exception:
            pass

    # Check package.json for name
    pkg_json = cwd / "package.json"
    if pkg_json.exists():
        try:
            import json
            data = json.loads(pkg_json.read_text())
            if "name" in data:
                name = data["name"].replace("@", "").replace("/", "-")
                return name
        except Exception:
            pass

    # Check pyproject.toml for name
    pyproject = cwd / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text()
            match = re.search(r'^name\s*=\s*["\'](.+?)["\']', content, re.MULTILINE)
            if match:
                return match.group(1)
        except Exception:
            pass

    # Fall back to folder name
    return cwd.name


def suggest_memories(
    project: Optional[str] = None,
    memory_dir: Optional[Path] = None,
    limit: int = 5,
    auto_detect: bool = True,
    json_output: bool = False,
) -> int:
    """
    Suggest relevant memories for the current project.

    Args:
        project: Project name. If None and auto_detect=True, auto-detect from PWD.
        memory_dir: Memory directory path
        limit: Maximum number of suggestions
        auto_detect: Whether to auto-detect project from PWD
        json_output: Output as JSON

    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        # Auto-detect project if needed
        if not project and auto_detect:
            project = detect_project()
            if project:
                print(f"Auto-detected project: {project}", file=sys.stderr)

        if not project:
            if json_output:
                import json
                print(json.dumps({"error": "No project specified and could not auto-detect", "suggestions": []}))
            else:
                print("Error: No project specified and could not auto-detect from current directory.", file=sys.stderr)
            return 1

        # Validate memory path
        validated_dir = validate_memory_path(memory_dir, force=False)
        config_path = validated_dir / "config.yaml"
        config = Config(config_path)
        db_path = config.database_path

        if not db_path.exists():
            if json_output:
                import json
                print(json.dumps({"error": "Memory not initialized", "suggestions": []}))
            else:
                print("Memory not initialized. Run 'memory init' first.", file=sys.stderr)
            return 1

        # Connect to database
        db = Database(db_path)
        db.connect()

        # Search for relevant memories from last 30 days
        keywords = ["port", "error", "convention", "command", "config", "setup", "install", "auth"]
        all_results = []

        for kw in keywords:
            results = db.search_memories(query=kw, project=project, limit=10)
            for r in results:
                r["relevance_keywords"] = kw
            all_results.extend(results)

        # Dedupe by id, sort by accessed_at, take top N
        seen = set()
        unique = []
        for r in sorted(all_results, key=lambda x: x.get("accessed_at", ""), reverse=True):
            if r["id"] not in seen:
                seen.add(r["id"])
                unique.append(r)

        suggestions = unique[:limit]

        db.close()

        # Output
        if json_output:
            import json
            print(json.dumps({
                "project": project,
                "count": len(suggestions),
                "suggestions": suggestions,
            }))
        else:
            if not suggestions:
                print(f"No memories found for project '{project}'.")
                return 0

            print(f"Top {len(suggestions)} memories for '{project}':")
            print("-" * 60)
            for i, m in enumerate(suggestions, 1):
                tags = ""
                if m.get("metadata"):
                    try:
                        import json
                        meta = json.loads(m["metadata"])
                        tags = ", ".join(meta.get("tags", []))
                    except Exception:
                        pass
                print(f"\n{i}. {m['content'][:100]}")
                if m.get("source"):
                    print(f"   Source: {m['source']} | Confidence: {m.get('confidence', 'N/A')}")
                if tags:
                    print(f"   Tags: {tags}")

        return 0

    except Exception as e:
        if json_output:
            import json
            print(json.dumps({"error": str(e), "suggestions": []}))
        else:
            print(f"Error suggesting memories: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Suggest relevant memories from current project")
    parser.add_argument("--project", "-p", default=None, help="Project name (auto-detected if not provided)")
    parser.add_argument("--limit", "-n", type=int, default=5, help="Maximum suggestions (default: 5)")
    parser.add_argument("--path", type=Path, default=None, help="Memory directory path")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    parser.add_argument("--no-auto-detect", action="store_true", help="Disable auto-detection")

    args = parser.parse_args()
    sys.exit(suggest_memories(
        project=args.project,
        memory_dir=args.path,
        limit=args.limit,
        auto_detect=not args.no_auto_detect,
        json_output=args.json,
    ))