# Contributing to Cheapskate Agent Memory

Thank you for your interest in improving CAM! This document provides guidelines for development.

## Quick Start

```bash
git clone https://github.com/canh0chua/Cheapskate-Agent-Memory.git
cd Cheapskate-Agent-Memory
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or venv\Scripts\activate  # Windows
pip install -e .
```

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-cov

# Run tests (testing mode allows temporary memory directories)
CHEAPSKATE_TESTING=1 pytest tests/ -v

# With coverage report
pytest tests/ --cov=src/cheapskate --cov-report=html
```

### Code Style

- Follow PEP 8
- Use type hints for all function parameters and returns
- Prefer explicit over implicit
- Keep functions small and focused

## Architecture Overview

Key files to understand first:

1. `src/cheapskate/config.py` - Configuration management (YAML-based)
2. `src/cheapskate/db.py` - Database layer (SQLite + FTS5)
3. `src/cheapskate/hrr.py` - Hyperdimensional Random Representation embeddings
4. `src/cheapskate/commands/` - CLI commands (init, add, list, search, topicify, etc.)
5. `src/cheapskate/memory_md.py` - MEMORY.md generation for Claude Code

## Development Workflow

1. Create a feature branch: `git checkout -b my-feature`
2. Make changes and add tests
3. Run tests locally until all pass
4. Commit with a conventional commit message:
   ```
   feat: add support for X
   fix: handle edge case in Y
   test: cover Z scenario
   docs: update README
   ```
5. Push and open a PR

### Commit Message Convention

We use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` new feature
- `fix:` bug fix
- `test:` test additions/modifications
- `docs:` documentation changes
- `refactor:` code restructuring
- `chore:` build/CI changes

## Testing Guidelines

- Write tests for new features
- Ensure all existing tests pass before PR
- Use fixtures in `tests/conftest.py` for common setup
- CLI tests: use `run_memory()` helper in `tests/test_cli.py`
- Database tests: use `temp_db` fixture for isolated DB

## Database Schema

CAM uses a single SQLite database with:

- `memories` - main table with content, embeddings, metadata
- `memories_fts` - FTS5 virtual table for full-text search
- `topics` - topic groupings
- `rules` - scope-based rules
- `audit` - audit trail for actions
- `state` - key-value store for last operations

FTS5 is configured as `content=memories` meaning it auto-updates when the memories table changes.

## Embedding (HRR) System

- `hrr.py` implements Hyperdimensional Random Representation encoding
- Embeddings are 512-dimensional float32 arrays, packed to bytes for storage
- `search_memories()` combines FTS5 lexical search with HRR semantic reranking
- Candidate pool: FTS5 returns `limit * 5` results, then reranked by cosine similarity

## Logging & Debugging

CAM uses `print()` for CLI output. For debugging:

- Add ` CHEAPSKATE_DEBUG=1` environment variable to enable verbose logging
- Check `~/.memory/` for config and database
- Use `memory status` to see current state

## CI/CD

GitHub Actions runs:

- Python 3.10, 3.12, 3.14
- `pytest` with coverage
- Lint (ruff/flake8) if configured

Make sure your code passes locally before pushing.

## Questions?

Open an issue or ask in the repository discussions.
