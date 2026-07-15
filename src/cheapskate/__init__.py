"""
Cheapskate Agent Memory.

A zero-cost, zero-dependency, fully-local memory system for coding agents.
"""

__version__ = "0.1.0"
__author__ = "canh0chua"
__email__ = "canh0chua@gmail.com"

from cheapskate.config import Config, load_config, validate_memory_path
from cheapskate.db import Database, get_database, init_database
from cheapskate.hooks import run_hooks
from cheapskate.hrr import encode, similarity
from cheapskate.client import MemoryClient

__all__ = [
    "Config",
    "load_config",
    "Database",
    "get_database",
    "init_database",
    "encode",
    "similarity",
    "validate_memory_path",
    "MAX_CONTENT_LENGTH",
    "MAX_PROJECT_LENGTH",
    "MAX_TAG_LENGTH",
    "MAX_TAGS_PER_MEMORY",
    "MemoryClient",
    "run_hooks",
]