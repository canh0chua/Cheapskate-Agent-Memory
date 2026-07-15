# Cheapskate Agent Memory

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Status](https://img.shields.io/badge/Status-Alpha-red.svg)

A **zero-cost, fully-local memory system for coding agents** — no cloud, no Ollama, no API fees. Built on SQLite + FTS5 + HRR vector search.

Inspired by Claude Code's memory, Holographic's LLM-free storage, and tiered memory resolution — but designed to run entirely offline on your local machine.

---

## Features

- **Zero-LLM storage tier** — Holographic Random Representation (HRR) vectors via pure math, no API calls
- **SQLite + FTS5** — instant full-text search with no external dependencies
- **Multi-strategy retrieval** — FTS5 keyword search + vector similarity + topic grouping fused together
- **Claude Code compatible** — generates `~/.claude/projects/<project>/memory/MEMORY.md` index files
- **Agent-driven capture** — call `memory add` during work sessions; no background watchers
- **Topic management** — group related memories into named topic files
- **Soft delete** — contradiction detection marks old facts instead of wiping them
- **Audit trail** — every memory change is logged with reason and timestamp
- **Auto-pilot for agents** — drop-in integration files make any coding agent self-drive CAM without native support

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         memory CLI                               │
├─────────────┬──────────────────┬─────────────────┬──────────────┤
│   SQLite    │      FTS5        │   HRR Vectors   │  Topic Files │
│   (core)    │  (full-text)     │  (similarity)   │  (markdown)  │
├─────────────┴──────────────────┴─────────────────┴──────────────┤
│                    ~/.memory/memory.db                           │
│                   ~/.claude/projects/*/memory/                   │
└─────────────────���───────────────────────────────────────────────┘
```

- **SQLite** — persistent storage for memories, topics, rules, and audit logs
- **FTS5** — SQLite's built-in full-text search engine for keyword queries
- **HRR (Holographic Reduced Representations)** — deterministic vector encoding via circular convolution, no model needed
- **FAISS** — optional vector index for fast approximate nearest-neighbor search on large corpora

---

## Installation

### From source

```bash
git clone https://github.com/canh0chua/Cheapskate-Agent-Memory.git
cd Cheapskate-Agent-Memory
pip install -e .
```

### Requirements

- Python 3.8+
- No external services required (fully offline)

---

## Quick Start

```bash
# 1. Initialize the memory database (creates ~/.memory/)
memory init

# 2. Add a memory entry
memory add "Backend runs on port 4000" -p myproject -t dev

# 3. Search memories
memory search "port 4000" -p myproject

# 4. List all memories for a project
memory list -p myproject

# 5. Auto-group memories into topics
memory topicify -p myproject

# 6. Generate the MEMORY.md index file
memory memory-md -p myproject
```

---

## CLI Reference

### `memory init [--path <dir>] [--force]`
Initialize the memory database. Creates `~/.memory/memory.db` with all tables and indexes.

```bash
memory init                           # default ~/.memory/
memory init --path /custom/path        # custom memory directory
memory init --force                   # reinitialize (destroys existing data)
```

### `memory add <content> [-p <project>] [-t <tags>] [-s <source>]`
Add a memory entry. Stores a natural-language fact with optional project and tags.

```bash
memory add "PostgreSQL uses port 5432" -p myproject -t database,infrastructure
memory add "Use pnpm, not npm" -p myproject -t conventions
memory add "API returns 422 on validation errors" -p api -t errors -s user
```

| Flag | Description | Default |
|------|-------------|---------|
| `-p, --project` | Project name | `default` |
| `-t, --tags` | Comma-separated tags | none |
| `-s, --source` | Source type: `user`, `agent`, `extracted`, `llm_consolidate` | `agent` |

### `memory list [-p <project>] [--all-projects] [-n <limit>]`
List memory entries, optionally filtered by project.

```bash
memory list                           # list from 'default' project
memory list -p myproject               # list from specific project
memory list --all-projects             # list across all projects
memory list -n 50                      # limit to 50 results
```

### `memory search <query> [-p <project>] [--all-projects] [-n <limit>] [-j]`
Full-text search across memory content using FTS5.

```bash
memory search "port"                  # search for 'port'
memory search "docker" -p myproject    # search with project filter
memory search "postgres" --all-projects -n 10   # cross-project, limited
memory search "error" -j               # JSON output
```

### `memory topicify [-p <project>] [-t <threshold>] [-g <strategy>] [-a]`
Auto-group memories into topics using clustering (tags, vector similarity, or keywords).

```bash
memory topicify -p myproject           # auto-group with default settings
memory topicify -p myproject -a        # auto-confirm without prompting
memory topicify -p myproject -g tags   # group by tags only
memory topicify -p myproject -t 0.5    # stricter similarity threshold
```

| Flag | Description | Default |
|------|-------------|---------|
| `-p, --project` | Project name | `default` |
| `-t, --threshold` | Similarity threshold (0.0–1.0) | `0.3` |
| `-g, --group-by` | Strategy: `auto`, `tags`, `vector`, `keywords` | `auto` |
| `-a, --auto` | Auto-create without prompting | `false` |

### `memory topic <action> [-p <project>]`
Manage topic files.

```bash
memory topic list                      # list all topics
memory topic create debugging -p myproject -m 1,2,3   # create from memory IDs
memory topic delete old-topic -p myproject -f         # delete (skip confirm)
```

Subcommands: `list`, `create <name>`, `delete <name>`

### `memory memory-md [-p <project>] [-f]`
Generate `MEMORY.md` index file for Claude Code compatibility (saved to `~/.claude/projects/<project>/memory/MEMORY.md`).

```bash
memory memory-md -p myproject         # generate for project
memory memory-md -p myproject -f      # overwrite existing
```

### `memory prune [-p <project>] [--dry-run]`
Prune old or contradicted memories based on config-driven decay settings.

```bash
memory prune                           # preview what would be deleted
memory prune -p myproject               # prune specific project
```

### `memory audit [-p <project>] [-a <action>] [-n <limit>]`
Show recent memory changes from the audit log.

```bash
memory audit                           # last 50 changes
memory audit -a add                    # filter by action type
memory audit -n 100                    # show 100 entries
```

Action types: `add`, `update`, `prune`, `contradict`, `access`

### `memory consolidate [-p <project>]`
Consolidate and synthesize memories using Claude Code. Summarizes recent memories, resolves contradictions, updates topic files, and regenerates `MEMORY.md`.

```bash
memory consolidate -p myproject
```

### `memory status`
Show memory database status, config summary, and last consolidate time.

```bash
memory status
```

### `memory stats [-p <project>]`
Show memory statistics — counts per project, per source, per tag.

```bash
memory stats                          # all projects
memory stats -p myproject              # specific project
```

---

## Agent Integration — Auto-Pilot

**No native integration required.** Drop in an instruction file and your coding agent auto-drives CAM.

```
integration/
├── AGENTS.md              ← generic instructions for any agent
├── CLAUDE-code/
│   └── CLAUDE.md          ← paste into Claude Code's ~/.claude/CLAUDE.md
└── hermes/
    └── SKILL.md           ← Hermes skill (copy to ~/.hermes/skills/)
```

### How it works

When an agent reads its instructions (CLAUDE.md, AGENTS.md, or a skill), it follows a self-driving loop:

```
Session start  →  memory search "context"   (load relevant facts)
       ↓
Agent discovers port/error/env/arch fact
       ↓
memory add "PostgreSQL on port 5432" -p myproject -t db
       ↓
End of meaningful session  →  memory topicify --auto
       ↓
Nightly cron  →  memory consolidate         (LLM synthesis, MEMORY.md update)
```

### What the agent auto-captures

The agent is instructed to call `memory add` when it discovers:

| Trigger | Example |
|---|---|
| Port numbers | "Backend on port 4000, PostgreSQL on 5432" |
| Error + fix pairs | "Error: ECONNREFUSED → restart docker-compose" |
| Non-standard commands | "Use `pnpm dev` not `npm run dev`" |
| Env vars that matter | "DB_HOST=localhost is used in config" |
| Architecture decisions | "API gateway pattern, auth via middleware" |
| Service names | "Docker Compose service named `db`, not `postgres`" |
| Config structures | "JWT secret goes in .env not config.yaml" |

### Claude Code

```bash
# Copy the ready-to-use instructions
cp integration/CLAUDE-code/CLAUDE.md ~/.claude/CLAUDE.md
```

Claude Code reads `~/.claude/CLAUDE.md` every session. It now knows to call `memory add` on the triggers above, run `memory search` at session start, and trigger consolidation.

### Hermes

```bash
# Copy the skill
cp -r integration/hermes ~/.hermes/skills/cheapskate-memory
```

The skill teaches Hermes the exact commands, trigger conditions, and pitfalls. Hermes loads it and auto-pilots CAM.

### Other Agents (OpenCode, Roo Cline, etc.)

Reference `integration/AGENTS.md` in the agent's system prompt, or adapt `integration/opencode/SKILL.md`.

---

## Configuration

Config file: `~/.memory/config.yaml`

```yaml
memory_dir: ~/.memory

capture:
  max_per_session: 50
  tags_whitelist: [db, infra, api, errors, dev]

forgetting:
  decay_days: 90          # prune if not accessed in 90 days
  max_age_days: 365        # hard delete anything older than 1 year
  include_contradicted: false
  soft_delete: true

consolidate:
  schedule: "0 2 * * *"   # cron: 2am daily
  trigger_threshold: 100   # trigger if 100+ new memories
```

---

## Design Philosophy

**No cloud. No Ollama. Zero cost.**

Cheapskate Agent Memory exists for developers who want persistent, searchable memory for their coding agents without:
- Paying for API calls on every read/write
- Running a local LLM server (Ollama, etc.)
- Storing data in a third-party cloud service
- Dealing with Docker or other runtime dependencies

The storage tier is completely offline. The only time you need an LLM is during `memory consolidate` — and that runs only on a schedule (e.g., once per night via cron), not on every query.

---

## File Layout

```
~/.memory/
├── memory.db           # SQLite database
├── config.yaml         # optional config overrides
└── memory.index        # FAISS vector index

~/.claude/projects/<project>/memory/
├── MEMORY.md           # generated index (for Claude Code)
├── topics/
│   ├── debugging.md
│   ├── api-conventions.md
│   └── ...
└── rules/
    ├── CLAUDE.md      # global rules
    ├── project.md
    └── local.md        # gitignored
```

---

## Contributing

Contributions welcome. Please ensure code passes linting before submitting PRs.

```bash
pip install -e ".[dev]"   # install with dev dependencies
ruff check .               # lint
pytest                     # run tests
```

---

## License

MIT License