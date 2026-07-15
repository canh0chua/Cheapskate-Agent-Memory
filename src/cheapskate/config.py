"""
Configuration management for Cheapskate Agent Memory.

Reads and validates config from ~/.memory/config.yaml (or custom path).
"""

import os
import pathlib
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


DEFAULT_CONFIG = """
capture:
  auto_capture:
    ports: true
    errors: true
    commands: true
    configs: true
    conventions: true
  max_per_session: 50
  tags_whitelist: []
consolidate:
  schedule: "0 2 * * *"
  trigger_threshold: 100
forgetting:
  decay_days: 90
  max_age_days: 365
  include_contradicted: false
  soft_delete: true
""".strip()


class Config:
    """Configuration manager for Cheapskate Agent Memory."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or self._default_config_path()
        self._data: Dict[str, Any] = {}
        self.load()

    def _default_config_path(self) -> Path:
        """Get default config path: ~/.memory/config.yaml"""
        home = pathlib.Path.home()
        return home / ".memory" / "config.yaml"

    def load(self) -> None:
        """Load config from file, or use defaults if not exists."""
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._data = yaml.safe_load(f) or {}
        else:
            # Use default config
            self._data = yaml.safe_load(DEFAULT_CONFIG) or {}

    def save(self) -> None:
        """Save current config to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(self._data, f, default_flow_style=False, sort_keys=False)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value using dot notation (e.g., 'capture.max_per_session')."""
        keys = key.split(".")
        value = self._data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value

    def set(self, key: str, value: Any) -> None:
        """Set a config value using dot notation."""
        keys = key.split(".")
        data = self._data
        for k in keys[:-1]:
            if k not in data:
                data[k] = {}
            data = data[k]
        data[keys[-1]] = value

    @property
    def memory_dir(self) -> Path:
        """Get the memory directory path."""
        return self.config_path.parent

    @property
    def database_path(self) -> Path:
        """Get the SQLite database path."""
        return self.memory_dir / "memory.db"


def load_config(config_path: Optional[Path] = None) -> Config:
    """Load configuration from file."""
    return Config(config_path)


def default_memory_dir() -> Path:
    """Get the default memory directory path."""
    return pathlib.Path.home() / ".memory"


def ensure_memory_dir(path: Optional[Path] = None) -> Path:
    """Ensure the memory directory exists."""
    memory_dir = path or default_memory_dir()
    memory_dir.mkdir(parents=True, exist_ok=True)
    return memory_dir