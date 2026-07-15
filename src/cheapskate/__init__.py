"""
Cheapskate Agent Memory.

A zero-cost, zero-dependency, fully-local memory system for coding agents.
"""

__version__ = "0.1.0"
__author__ = "canh0chua"
__email__ = "canh0chua@gmail.com"

from cheapskate.config import Config, load_config
from cheapskate.db import Database, get_database, init_database
from cheapskate.hrr import encode, similarity

__all__ = [
    "Config",
    "load_config",
    "Database",
    "get_database",
    "init_database",
    "encode",
    "similarity",
]