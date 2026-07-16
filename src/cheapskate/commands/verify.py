"""
memory verify command - re-verify stored memories and flag stale facts.
"""

import json
import re
import shutil
import socket
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cheapskate.config import Config
from cheapskate.db import Database

PORT_PATTERN = re.compile(r"\bport\s+(\d+)\b", re.IGNORECASE)
COMMAND_PATTERN = re.compile(r"`([^`]+)`")
URL_PATTERN = re.compile(r"https?://\S+")
PATH_PATTERN = re.compile(r"(?<![\w\"'/`])(/[\w./\-]+)")
IP_PORT_PATTERN = re.compile(r"\b(\d{1,3}(?:\.\d{1,3}){3}):(\d+)\b")


def _check_port(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _check_port_pattern(content: str) -> Optional[Tuple[str, str]]:
    match = PORT_PATTERN.search(content)
    if match:
        return match.group(1), match.group(0)
    match = IP_PORT_PATTERN.search(content)
    if match:
        return match.group(2), match.group(0)
    return None


def _check_command_pattern(content: str) -> Optional[str]:
    match = COMMAND_PATTERN.search(content)
    if match:
        cmd = match.group(1).strip()
        return cmd.split()[0] if cmd else cmd
    return None


def _check_url_pattern(content: str) -> Optional[str]:
    match = URL_PATTERN.search(content)
    if match:
        return match.group(0)
    return None


def _check_path_pattern(content: str) -> Optional[str]:
    match = PATH_PATTERN.search(content)
    if match:
        path = match.group(1)
        if len(path) > 3 and path.startswith("/"):
            return path
    return None


def _check_url(url: str, timeout: float = 3.0) -> Tuple[bool, str]:
    """Check if a URL is reachable using stdlib urllib."""
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status < 400, f"HTTP {resp.status}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception:
        return False, "request failed"


def verify_memories(
    memory_dir: Optional[Path] = None,
    project: str = "default",
    json_output: bool = False,
) -> int:
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

        memories = db.list_memories(project=project, limit=500)
        results: List[Dict[str, Any]] = []

        for mem in memories:
            memory_id = mem.get("id")
            content = mem.get("content", "")
            status = "unknown"
            reason = "no verifiable pattern"

            port = _check_port_pattern(content)
            if port:
                port_num, _ = port
                if _check_port("127.0.0.1", int(port_num)):
                    status = "verified"
                    reason = f"port {port_num} is listening"
                else:
                    status = "stale"
                    reason = f"port {port_num} is not listening"
                results.append({
                    "memory_id": memory_id,
                    "content": content,
                    "status": status,
                    "reason": reason,
                })
                continue

            cmd = _check_command_pattern(content)
            if cmd:
                found = shutil.which(cmd)
                status = "verified" if found else "stale"
                reason = f"command '{cmd}' {'found' if found else 'not found'} in PATH"
                results.append({
                    "memory_id": memory_id,
                    "content": content,
                    "status": status,
                    "reason": reason,
                })
                continue

            path = _check_path_pattern(content)
            if path:
                exists = Path(path).exists()
                status = "verified" if exists else "stale"
                reason = f"path '{path}' {'exists' if exists else 'does not exist'}"
                results.append({
                    "memory_id": memory_id,
                    "content": content,
                    "status": status,
                    "reason": reason,
                })
                continue

            url = _check_url_pattern(content)
            if url:
                ok, msg = _check_url(url)
                status = "verified" if ok else "stale"
                reason = msg
                results.append({
                    "memory_id": memory_id,
                    "content": content,
                    "status": status,
                    "reason": reason,
                })
                continue

            results.append({
                "memory_id": memory_id,
                "content": content,
                "status": status,
                "reason": reason,
            })

        db.close()

        if json_output:
            print(json.dumps({"project": project, "results": results}))
        else:
            print(f"Memory verification for project: {project}")
            print(f"Total memories checked: {len(results)}")
            for item in results:
                status_icon = "✓" if item["status"] == "verified" else "✗" if item["status"] == "stale" else "?"
                print(f"[{status_icon}] #{item['memory_id']}: {item['reason']}")
                print(f"    {item['content'][:120]}")

        return 0

    except Exception as e:
        print(f"Error verifying memories: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Verify stored memories")
    parser.add_argument("--project", "-p", default="default", help="Project name")
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Memory directory path (default: ~/.memory)",
    )
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")

    args = parser.parse_args()
    sys.exit(verify_memories(project=args.project, memory_dir=args.path, json_output=args.json))
