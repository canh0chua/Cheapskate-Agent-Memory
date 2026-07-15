"""
Hook system for Cheapskate Agent Memory.

Allows agents to run custom hooks on events like session start, error, file edit, etc.
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from cheapskate.config import Config

logger = logging.getLogger("cheapskate")


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

            if output_mode == "silent":
                with open(os.devnull, "w") as devnull:
                    subprocess.run(command, shell=True, stdout=devnull, stderr=devnull, timeout=10)
            else:
                subprocess.run(command, shell=True, timeout=10)

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