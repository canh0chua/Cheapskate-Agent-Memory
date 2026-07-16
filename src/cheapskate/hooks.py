"""
Hook system for Cheapskate Agent Memory.

Allows agents to run custom hooks on events like session start, error, file edit, etc.
"""

import logging
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from cheapskate.config import Config

logger = logging.getLogger("cheapskate")


def _validate_command(command: str) -> bool:
    """
    Validate that a hook command is safe to execute.

    Blocks shell metacharacters that enable injection.
    Returns True if safe, False if potentially dangerous.
    """
    # Block shell metacharacters that enable injection
    dangerous = [";", "&&", "||", "|", "$(", "`", "${", ">", "<", ">>", "2>&1"]
    for char in dangerous:
        if char in command:
            logger.warning(f"Blocked unsafe hook command (contains '{char}'): {command}")
            return False
    return True


def run_hooks(event: str, project: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> None:
    """
    Run hooks for a given event.

    Args:
        event: Event name (on_session_start, on_error, on_file_edit, on_session_end)
        project: Project name
        context: Additional context for hook substitution
    """
    if context is None:
        context = {}

    context.setdefault("project", project or "default")

    try:
        config_path = Path.home() / ".memory" / "config.yaml"
        if not config_path.exists():
            return

        config = Config(config_path)
        hooks = config.get(f"hooks.{event}", [])

        if not hooks:
            return

        for hook in hooks:
            if isinstance(hook, dict):
                command = hook.get("command", "")
                output_mode = hook.get("output", "silent")
            else:
                command = str(hook)
                output_mode = "silent"

            # Substitute placeholders
            for key, value in context.items():
                command = command.replace(f"{{{key}}}", str(value))

            # Validate command safety
            if not _validate_command(command):
                continue

            # Parse command safely (no shell=True)
            try:
                args = shlex.split(command)
            except ValueError as e:
                logger.warning(f"Failed to parse hook command: {e}")
                continue

            if not args:
                continue

            if output_mode == "silent":
                with open(os.devnull, "w") as devnull:
                    subprocess.run(args, stdout=devnull, stderr=devnull, timeout=10)
            else:
                subprocess.run(args, timeout=10)

            logger.debug(f"Ran hook for {event}: {command}")

    except Exception as e:
        logger.warning(f"Hook error for {event}: {e}")


def list_hooks(config_path: Optional[Path] = None) -> Dict[str, List[str]]:
    """List all configured hooks."""
    if config_path is None:
        config_path = Path.home() / ".memory" / "config.yaml"

    if not config_path.exists():
        return {}

    config = Config(config_path)
    events = ["on_session_start", "on_error", "on_file_edit", "on_session_end"]
    return {event: config.get(f"hooks.{event}", []) for event in events}
