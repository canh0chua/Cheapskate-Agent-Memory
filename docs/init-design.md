# Cheapskate Agent Memory — Detailed Design

## What is Cheapskate Agent Memory (CAM)?

A zero-cost, zero-dependency, fully-local memory system for coding agents.

Inspired by Claude Code's memory, Holographic's LLM-free storage, and OpenViking's tiered resolution — but built to run without Docker, Ollama, or any external services.

1. **Zero-LLM storage tier** — Holographic approach: SQLite + FTS5 + vector algebra (HRR or approximate nearest neighbor). No API calls, no network, instant.
2. **Claude Code-compatible file layout** — `~/.claude/projects/<project>/memory/` with `MEMORY.md` index and topic files.
3. **Agent-driven capture** — Coding agent calls `memory add` during work; no background watcher.
4. **Scheduled consolidation** — Cron triggers an agent run to call LLM *only then* for Dreams-style synthesis.
5. **Multi-strategy retrieval** — Combines: FTS5 exact, vector similarity, topic lookup, rules injection.
6. **Tiered resolution** — Load abstract → overview → full on demand (OpenViking idea) for large memories.

---

## Database Schema

```sql
-- Raw memory entries (facts, observations, extracted entities)
CREATE TABLE memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    accessed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    source TEXT NOT NULL,       -- 'user', 'agent', 'extracted', 'llm_consolidate'
    content TEXT NOT NULL,      -- natural language fact
    embedding BLOB,             -- optional vector (HRR or float array)
    metadata TEXT,              -- JSON: {tags, entities, confidence, ...}
    abstract TEXT,              -- generated during consolidation (short summary)
    confidence REAL DEFAULT 0.5,
    contradicted_by INTEGER REFERENCES memories(id),
    created DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Full-text search index (FTS5) on content
CREATE VIRTUAL TABLE memories_fts USING fts5(
    content,
    project,
    content=memories,
    content_rowid=id
);

-- Topics (like Claude Code topic files)
CREATE TABLE topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project TEXT NOT NULL,
    name TEXT NOT NULL,       -- e.g. 'debugging', 'api-conventions'
    summary TEXT,             -- short description
    memory_ids TEXT,          -- JSON array of linked memory IDs
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project, name)
);

-- Rules (CLAUDE.md style instructions that always load)
CREATE TABLE rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project TEXT NOT NULL,
    scope TEXT NOT NULL,      -- 'global', 'user', 'project', 'local'
    content TEXT NOT NULL,
    priority INTEGER DEFAULT 0
);

-- Audit trail for all memory changes
CREATE TABLE audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id INTEGER REFERENCES memories(id),
    action TEXT NOT NULL CHECK(action IN ('add', 'update', 'prune', 'contradict', 'access')),
    reason TEXT,              -- 'decay', 'contradiction', 'manual', 'query'
    agent_id TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT             -- JSON with additional context
);

-- State table for consolidation timestamps etc.
CREATE TABLE IF NOT EXISTS state (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Session summaries for continuity between sessions
CREATE TABLE IF NOT EXISTS session_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project TEXT NOT NULL,
    date DATETIME DEFAULT CURRENT_TIMESTAMP,
    summary TEXT NOT NULL
);
```

**Indexes:**
- `idx_memories_project`: memories(project)
- `idx_memories_accessed`: memories(accessed_at)
- `idx_memories_source`: memories(source)
- `idx_topics_project`: topics(project)
- `idx_rules_project_scope`: rules(project, scope)
- `idx_audit_memory`: audit(memory_id)

**Migrations:** Existence checks add `abstract` and `confidence` columns to existing databases at schema init.

---

## File Layout (Claude Code Compatible)

```
~/.claude/projects/<project>/memory/
├── MEMORY.md              # Concise index (25KB/200 lines cap) — always loaded
├── topics/
│   ├── debugging.md
│   ├── api-conventions.md
│   └── ...
└── rules/
    ├── CLAUDE.md          # Global rules (copied from DB on refresh)
    ├── project.md
    └── local.md           # gitignored
```

**MEMORY.md format:**
```markdown
# Memory Index — <project>

## Topics
- [debugging](topics/debugging.md) — breakpoints, logs, common errors
- [api-conventions](topics/api-conventions.md) — REST design, auth, errors

## Recent Facts (auto-generated)
- Port 4000 used for local dev (2025-06-15)
- Docker Compose uses service name 'db' for PostgreSQL
- ...

## Quick Reference
- Run tests: `pytest -n auto`
- Lint: `ruff .`
```

Each topic file contains organized, summarized content from linked memory entries.

---

## Capture API

**Tool:** `memory add <content> [--project <proj>] [--tags tag1,tag2] [--entities "entities JSON"]`

- Agent calls this during coding sessions to store facts.
- Stores raw text to `memories`.
- Optionally computes vector embedding (if configured) using a local deterministic transform (HRR) or a cached embedding from a local model run once per session.
- Immediately writes; no waiting for consolidation.

**Example agent call:**
```bash
memory add "Port 4000 is used by the backend service" --project myapp --tags "dev,ports"
```

---

## Query API

**Tool:** `memory query "<query>" [--project <proj>] [--limit N] [--strategy <fuse|fts|vector|topic>]`

Retrieves ranked memories using multiple strategies:

1. **FTS5** — exact keyword matches (ports, error codes, filenames)
2. **Vector** — semantic similarity (requires embedding on query, compute dot-product)
3. **Topic expansion** — if query matches a topic name, load that topic file entirely
4. **Rules injection** — always load matching rules into context

Results are fused (BM25-like scores normalized) and deduped.

**Output format:**
```json
{
  "results": [
    {"id": 123, "content": "...", "score": 0.87, "source": "vector"},
    ...
  ]
}
```

---

## Topic Manager

**Agent tool:** `memory topicify [--project <proj>] [--auto]`

- Groups related memories (by tags, entities, or semantic similarity)
- Creates/updates topic files under `topics/`
- Summarizes group into a coherent markdown file with cross-references
- Updates `topics` table with linked memory IDs

**Manual mode:** `memory topic create <name> --memory-ids 12,34,56`

---

## Memory Tasks

The agent performs 6 types of memory operations. All are invoked as tool calls during the agent's normal workflow.

| Task | Command | Trigger | Who initiates |
|------|---------|---------|---------------|
| Capture | `memory add` | Agent discovers a fact | Agent (auto) or User (explicit) |
| Retrieve | `memory query` | Agent needs context | Agent (auto at session start) |
| Search | `memory search` | Ad-hoc keyword lookup | Agent or User |
| Topic | `memory topicify` | Group related memories | Agent (cron job) |
| Consolidate | `memory consolidate` | Dreams synthesis | Agent (cron job) |
| Rules | `memory rule add` | Add persistent instruction | User or Agent |

---

## Capture Logic

### Three Capture Modes

```
Mode 1 — User-driven (explicit)
─────────────────────────────────
User: "Remember that we use pnpm here"
Agent: memory add "Project uses pnpm, not npm" --project myapp --tags conventions
       → stored immediately
```

```
Mode 2 — Agent auto-capture (heuristic-based)
────────────────────────────────────────────
Agent runs: docker compose ps
Discovers: PostgreSQL on port 5432
Heuristic fires: new port + new service → worth remembering
Agent: memory add "PostgreSQL via Docker Compose on port 5432" --tags "db,infrastructure"
       → stored immediately
```

```
Mode 3 — Silent capture (config-driven, no user action)
──────────────────────────────────────────────────────
~/.memory/config:
  auto_capture:
    ports: true        # any port mentioned → auto-add
    errors: true       # error + fix pair → auto-add
    commands: true     # non-standard commands → auto-add
    configs: true      # env vars, package.json deps → auto-add
    conventions: true  # pattern used 3x → add it
```

### What Qualifies as "Worth Remembering"

For a coding agent specifically:

```
✅ Added to memory:
  • Port numbers (e.g., "backend runs on 4000")
  • Error codes + fix pairs
  • Non-standard commands (not npm install, but custom scripts)
  • Env vars that matter
  • Package manager (pnpm, bun, not npm)
  • Test framework + command patterns
  • Auth config structure
  • API response shapes
  • Architecture decisions made during session
  • Service names in docker compose

❌ NOT added:
  • Generic programming facts (syntax, stdlib)
  • Already-known patterns (npm ci, standard pytest)
  • Ephemeral session facts (file path, cursor position)
  • User preferences that belong in CLAUDE.md
```

### Overlap: Memory vs CLAUDE.md

```
CLAUDE.md  → persistent user/team instructions
            "always use pnpm", "prefer functional components"

Memory     → project-derived facts discovered during work
            "port 4000", "postgres service named 'db'", "error X means Y"
```

The boundary: if the user *decided* it → CLAUDE.md. If the agent *discovered* it → memory.

### User Control

Configured in `~/.memory/config`:

```yaml
capture:
  auto_capture:
    ports: true
    errors: true
    commands: true
    configs: true
    conventions: true
  max_per_session: 50       # prevent flooding
  tags_whitelist: [db, infra, api, errors]
  project_overrides:
    myapp:
      auto_capture: false   # disable for specific project

consolidate:
  schedule: "0 2 * * *"     # cron: 2am daily
  trigger_threshold: 100    # also trigger if 100+ new memories

forgetting:
  decay_days: 90           # prune if not accessed in N days (0 = disabled)
  max_age_days: 365        # hard delete anything older than N days (0 = disabled)
  include_contradicted: false  # show contradicted memories in queries
  soft_delete: true         # move to audit, don't hard delete
```

---

## Consolidation Pipeline (Cron-Driven)

**Entry:** `memory consolidate [--project <proj>]`

Triggered by cron (e.g., daily). Runs the **coding agent** in a special mode:

```
1. Load new memories since last consolidate
2. Run LLM (Claude Code or Ollama) with prompt:
   - Summarize facts per topic
   - Resolve contradictions
   - Update topic files
   - Rewrite MEMORY.md index (under 25KB)
3. Optionally regenerate embeddings for summaries (vector update)
4. Record consolidation timestamp
```

**Dreams-style prompt skeleton:**
```
You are a memory curator. Below are new memories added since last consolidation.

[Memory list...]

Tasks:
1. For each existing topic, integrate new facts.
2. Create new topics if needed.
3. Detect and resolve contradictions.
4. Rewrite each topic file to be concise and useful.
5. Update MEMORY.md index (stay under 25KB).

Output: updated topic files + MEMORY.md.
```

**Cron example:**
```bash
0 2 * * * coding-agent --task memory_consolidate --project myapp >> ~/.memory/cron.log 2>&1
```

---

## Agent Session Flow

```
User starts coding session
  │
  ├─→ Agent calls: memory query "context about this project"
  │           ← returns MEMORY.md index + relevant facts
  │
  ├─→ Agent works, self-captures when heuristics fire
  │           memory add "PostgreSQL on port 5432" --tags db
  │
  ├─→ User can say "remember..." at any time
  │
  └─→ Session ends
              │
              ▼
        Cron fires (nightly)
              │
  ├─→ Agent runs: memory consolidate
  │   • LLM reads new memories
  │   • Updates topic files
  │   • Rewrites MEMORY.md index
  │   • Syncs rules → CLAUDE.md files
  │
  └─→ Next session: Claude Code loads MEMORY.md + topic files
```

---

## Aggressive Forgetting Mechanisms

Memory bloat is the silent killer. Cheapskate includes three defensive measures, all driven by `~/.memory/config`.

### Time-based Decay (Config-driven)

Decay parameters in `~/.memory/config`:

```yaml
forgetting:
  decay_days: 90           # prune if not accessed in N days (0 = disabled)
  max_age_days: 365        # hard delete anything older than N days (0 = disabled)
  include_contradicted: false  # show contradicted memories in queries
  soft_delete: true         # move to audit, don't hard delete
```

How it works:
1. Every `memory query` call updates `accessed_at` for returned memories
2. A nightly `memory prune` command (run as part of consolidate or standalone cron) scans:
   - `accessed_at < NOW() - decay_days` → mark for pruning
   - `timestamp < NOW() - max_age_days` → hard cap (even if accessed recently)
3. All deletions logged to `audit` table (never permanently wiped)
4. Soft delete via `contradicted_by` field when applicable

### Contradiction Detection

During consolidation, the LLM is prompted to:
1. Scan all memories on the same topic
2. Flag contradictory statements (e.g., "port 4000" vs "port 5000")
3. Resolve by:
   - Preferring the most recent fact
   - Preferring explicit user statements over agent discoveries
   - Marking the older fact as `contradicted_by` (soft delete, stays in audit)

The `memories` table gets:
```sql
ALTER TABLE memories ADD COLUMN contradicted_by INTEGER REFERENCES memories(id);
```

In queries, contradicted memories are ranked lower or filtered by config flag `forgetting.include_contradicted` (default false).

### Source Citations & Audit Trail

Every memory must have a `source` field:
- `user` — explicitly requested by user ("remember that...")
- `agent` — auto-captured by heuristics
- `extracted` — pulled from code/config by agent parsing
- `llm_consolidate` — generated during Dreams (has linked memory IDs)

The `audit` table logs every change:
```sql
CREATE TABLE audit (
    id INTEGER PRIMARY KEY,
    memory_id INTEGER,
    action TEXT, -- 'add', 'update', 'prune', 'contradict'
    reason TEXT, -- 'decay', 'contradiction', 'manual'
    agent_id TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT  -- JSON with additional context
);
```

This prevents incorrect information from silently overwriting correct facts — you can always trace who changed what and why.

---

## Integration with Claude Code

Claude Code automatically loads:
- `~/.claude/CLAUDE.md` → we sync global rules from DB to this file on consolidate
- `./CLAUDE.md` and `./CLAUDE.local.md` → project-specific rules
- `~/.claude/projects/<project>/memory/MEMORY.md` → our generated index
- Topic files referenced in `MEMORY.md` → loaded on demand

**Rule sync job:** Part of consolidation copies DB `rules` where `scope='global'` to `~/.claude/CLAUDE.md`; `scope='project'` to project `CLAUDE.md`.

---

## Implementation Phases

**Phase 1 — Storage & Capture (MVP)**
- Set up SQLite schema + FTS5
- `memory add` command (standalone CLI)
- Simple `memory list` and `memory search` (FTS5 only)

**Phase 2 — Vector Layer**
- Integrate deterministic embedding (HRR) or local `all-MiniLM-L6-v2` via Ollama (offline)
- `memory query` with vector + FTS5 fusion
- Index maintenance (update embeddings on add)

**Phase 3 — Topic Manager**
- `memory topicify` (agent-driven)
- Topic file writer (markdown)
- `topics` table maintenance

**Phase 4 — Consolidation Pipeline**
- `memory consolidate` with agent + LLM
- Dreams prompt engineering
- MEMORY.md generator (25KB cap truncation strategy)
- Rule sync to CLAUDE.md files

**Phase 5 — CLI Polish**
- `memory status` (stats, last consolidate time)
- `memory stats` (counts per project, per tag)
- Shell completions (bash, zsh, fish)
- Config validation

**Phase 6 — Advanced**
- Tiered resolution (abstracts/overviews)
- Pruning and archiving
- Cross-project queries
- Web UI (optional)

---

## Current Status (as of 2026-07-16)

- ✅ **Phase 1-5 complete** — all core features implemented
- ✅ **Zero external dependencies** — uses only Python standard library + numpy (for HRR)
- ✅ **Production-ready** — 166 tests passing
- ✅ **Python API** (`MemoryClient`) available
- ✅ **MCP server** (`python -m cheapskate.mcp`) available
- ✅ **JSON output** on all commands

**Open Questions** (resolved or superseded):
1. **Embedding strategy**: HRR (pure math) chosen over local transformer. Good for zero-deps, deterministic.
2. **Vector storage**: Not used at scale yet; HRR embeddings stored as BLOBs in `memories` table.
3. **Consolidation frequency**: Daily (cron).
4. **FAISS**: Not implemented; design remains for future Phase 6.
5. **MiniLM via Ollama**: Not needed; HRR provides LLM-free storage tier.

---

## Success Metrics

- **Capture latency** < 50ms (pure SQLite insert)
- **Query latency** < 200ms (FTS5+vector on 10K memories)
- **MEMORY.md** stays ≤ 25KB automatically
- **Consolidation** completes within token budget (Claude Sonnet 200K context should handle 1K new memories)
- **Zero network calls** during normal operation (storage tier fully offline)

---

**Tech Stack**

- Language: Python 3.8+
- Storage: SQLite (built-in)
- Search: FTS5 (built-in)
- Vectors: HRR (numpy for array math)
- LLM integration: Claude Code (subprocess) or Ollama (HTTP) — optional
