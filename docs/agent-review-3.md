# Cheapskate Agent Memory — Roadmap Plan (Review 3)

**Created:** 2026-07-15
**Author:** Hermes Agent
**Status:** Active — items being addressed in parallel
**Based on:** agent-review-1.md, agent-review-2.md, integration gap analysis

---

## Executive Summary

CAM's code quality is solid (9.5/10) but its **agent integration is documentation-driven, not architecture-driven**. Agents can't treat CAM as a first-class memory system — they must manually invoke CLI heuristics. This roadmap closes that gap in three phases.

**Health Score:** 9.5/10 (code) → 5/10 (integration)

---

## Integration Gap Analysis

### What's Broken

| Gap | Severity | Impact |
|---|---|---|
| No Python API | 🔴 Critical | Every `memory add` spawns a new Python process (~100ms overhead). Agents running in Python must `subprocess.run` instead of `import cheapskate`. |
| No JSON output | 🔴 Critical | Agents parse stdout — fragile, breaks on formatting changes, locale differences |
| No native hooks | 🔴 Critical | Agent must *remember* to call heuristics — no auto-capture on error, file edit, session start |
| No confidence/provenance | 🟡 High | Agent can't weight memories: `user` > `agent` > `extracted` |
| No session continuity | 🟡 High | No standard `## Last Session` section for cross-session wake-up |
| No `memory suggest` | 🟡 High | Agent must search — CAM should proactively surface relevant memories from PWD |
| Thin SKILL.md files | 🟡 Medium | Docs, not executable prompts — agents get instructions, not templates |
| No integration tests | 🟡 Medium | Agent workflows aren't tested end-to-end |

### What's Good

- `AGENTS.md` heuristics are solid
- Agent-specific wrappers exist (`CLAUDE.md`, `hermes/SKILL.md`, `opencode/SKILL.md`)
- MEMORY.md generation for Claude Code is the right idea
- CLI is functional and scriptable

---

## Phase 1 — Quick Wins (1-2 days)

**Goal:** Enable agents to import CAM as a library, not orchestrate it as a CLI.

### 1.1 Python API — `MemoryClient` class

**Priority:** 🔴 Critical
**File:** `src/cheapskate/client.py` (new)

```python
from cheapskate import MemoryClient

mem = MemoryClient()  # reads ~/.memory/config.yaml automatically

# Add
mem.add("PostgreSQL on port 5432", project="myapp", tags=["infra", "db"])

# Search (returns structured dicts)
results = mem.search("port", project="myapp")
# [{id: 1, content: "...", score: 0.95, source: "agent", ...}, ...]

# List
memories = mem.list(project="myapp", limit=20)

# Stats
stats = mem.stats(project="myapp")
# {memories: 142, topics: 8, last_consolidate: "...", ...}
```

**Acceptance criteria:**
- `from cheapskate import MemoryClient` works
- All CLI commands have equivalent client methods
- Client is thread-safe (uses WAL mode)
- Tests cover all client methods

### 1.2 JSON output for all CLI commands

**Priority:** 🔴 Critical
**Files:** `src/cheapskate/commands/search.py`, `list.py`, `stats.py`, `status.py`

```bash
memory search "port" --project myapp --json
# {"results": [...], "count": 5, "query": "port", "project": "myapp"}

memory list --project myapp --json
# {"memories": [...], "count": 20, "project": "myapp"}

memory stats --project myapp --json
# {"memories": 142, "topics": 8, "sources": {...}, ...}
```

**Acceptance criteria:**
- `--json` flag on all commands that produce output
- Valid JSON on stdout, errors on stderr
- No color codes in JSON mode (set `NO_COLOR=1`)

### 1.3 Confidence + Provenance tracking

**Priority:** 🟡 High
**Files:** `src/cheapskate/db.py`, `src/cheapskate/commands/add.py`

Add `confidence` column to `memories` table:
```sql
ALTER TABLE memories ADD COLUMN confidence REAL DEFAULT 0.5;
```

Default confidence by source:
- `source='user'` → confidence = 1.0
- `source='agent'` → confidence = 0.7
- `source='extracted'` → confidence = 0.5
- `source='llm_consolidate'` → confidence = 0.6

Search results sorted by: `(confidence * 0.3) + (similarity_score * 0.7)`

### 1.4 Update AGENTS.md with Python API examples

**Priority:** 🟡 High
**File:** `integration/AGENTS.md`

Add section showing Python API usage:
```python
from cheapskate import MemoryClient
mem = MemoryClient()

# Session start
context = mem.search("context", project="myapp")
for m in context:
    print(f"[{m['source']}] {m['content']}")
```

---

## Phase 2 — Medium-term (1 week)

**Goal:** Make CAM proactive, not just reactive.

### 2.1 Hook system in config.yaml

**Priority:** 🔴 Critical
**File:** `src/cheapskate/config.py`, `src/cheapskate/hooks.py` (new)

```yaml
hooks:
  on_session_start:
    - command: "memory search context --project {project}"
      output: print  # or: inject, silent
  on_error:
    - command: "memory add {error} --project {project} --tags errors"
      output: silent
  on_file_edit:
    - command: "memory add {summary} --project {project} --tags changes"
      output: silent
  on_session_end:
    - command: "memory topicify --project {project} --auto"
      output: silent
```

**Acceptance criteria:**
- Hooks defined in `~/.memory/config.yaml`
- CAM provides `run_hooks(event, context)` function
- Agents call `run_hooks("session_start", project="myapp")` at session start
- Hooks are non-blocking (failures logged, not propagated)

### 2.2 `memory suggest --from-pwd`

**Priority:** 🟡 High
**Files:** `src/cheapskate/commands/suggest.py` (new)

Auto-discover project from current working directory and surface relevant memories:

```bash
cd ~/my-project
memory suggest
# → Detects project from .git/config or folder name
# → Searches for relevant memories (ports, errors, conventions)
# → Returns top 5 most relevant + recent
```

**Acceptance criteria:**
- Detects project from: `.git/config`, `package.json`, `pyproject.toml`, folder name
- Returns memories from last 30 days, sorted by relevance + recency
- Works without explicit `--project` flag

### 2.3 Executable SKILL.md templates

**Priority:** 🟡 Medium
**Files:** `integration/hermes/SKILL.md`, `integration/opencode/SKILL.md`, `integration/CLAUDE-code/CLAUDE.md`

Convert from documentation to **executable prompt templates**:

```markdown
## Session Start Workflow

When you start a new session in a project:

1. Detect project name from: .git/config, package.json, folder name
2. Run: `memory suggest --from-pwd`
3. For each returned memory, acknowledge it silently
4. If no memories found, run: `memory search "context" --project {project}`

## Capture Workflow

When you discover a worth-knowing fact:
1. Run: `memory add "{fact}" --project {project} --tags {tags}`
2. If this is the 5th capture in this session, run: `memory topicify --project {project} --auto`
```

### 2.4 Integration tests for agent workflows

**Priority:** 🟡 Medium
**Files:** `tests/test_agent_integration.py` (new)

Test each agent type's workflow:
- Claude Code: MEMORY.md loading, CLAUDE.md sync
- Hermes: cron job integration, hook system
- OpenCode: skill file loading

```python
def test_memory_md_loads_into_context():
    """Verify MEMORY.md content is readable and parseable."""
    ...

def test_claude_md_sync_rules():
    """Verify consolidate syncs rules to CLAUDE.md."""
    ...
```

---

## Phase 3 — Long-term (2-4 weeks)

**Goal:** CAM becomes a first-class memory extension of the agent.

### 3.1 Native Hermes integration

**Priority:** 🔴 Critical
**Files:** Hermes plugin or MCP server

Expose CAM as an MCP (Model Context Protocol) server:

```json
// Hermes config.yaml
mcp:
  servers:
    cheapskate:
      command: "python -m cheapskate.mcp"
      # or: pip install cheapskate[mcp]
```

Tools exposed:
- `memory_add` — add memory
- `memory_search` — search with hybrid ranking
- `memory_suggest` — proactive suggestions from PWD
- `memory_topicify` — auto-group memories
- `memory_consolidate` — LLM synthesis

### 3.2 Memory verification loop

**Priority:** 🟡 Medium
**Files:** `src/cheapskate/commands/verify.py` (new)

Periodically re-verify memories:
- Check if referenced ports/services still exist
- Flag stale facts
- Suggest corrections

```bash
memory verify --project myapp
# → "Port 4000: still in use ✓"
# → "Service 'db': still exists ✓"
# → "Custom command 'pnpm test:unit': NOT FOUND — command may have changed"
```

### 3.3 Session continuity protocol

**Priority:** 🟡 Medium
**Files:** `src/cheapskate/memory_md.py`

Add `## Last Session` section to MEMORY.md:

```markdown
## Last Session (2026-07-15)

Worked on: Authentication refactor
Discovered: JWT secret in .env.local, not .env
Next steps: Move secret to .env, update auth middleware
```

**Acceptance criteria:**
- `consolidate` writes last session summary
- `suggest` includes last session context
- Agent reads last session at session start

### 3.4 Ollama fallback for consolidation

**Priority:** 🟡 Medium
**Files:** `src/cheapskate/commands/consolidate.py`

Abstract LLM backend:

```python
def consolidate(project, llm="claude"):
    if llm == "claude":
        return run_claude(prompt)
    elif llm == "ollama":
        return run_ollama(prompt, model="llama3")
    elif llm == "offline":
        return offline_summarize(memories)  # template-based
```

Config:
```yaml
consolidate:
  backend: "claude"  # or "ollama", "offline"
  ollama_url: "http://localhost:11434"
  ollama_model: "llama3"
```

### 3.5 Cross-project memory queries

**Priority:** 🟡 Low
**Files:** `src/cheapskate/commands/search.py`

```bash
memory search "postgres" --all-projects
# Returns memories from all projects, tagged with project name
```

---

## Open Issues from Review 2

These are being fixed in parallel (subagent `deleg_46ae65e4`):

| # | Issue | File | Status |
|---|---|---|---|
| 1 | Topicify auto mode vector logic bug | `commands/topicify.py:278` | 🔄 Fixing |
| 2 | Consolidation subprocess no timeout | `commands/consolidate.py:96` | 🔄 Fixing |
| 3 | FTS5 over-sanitization ("C++" → "C") | `db.py:_sanitize_fts_query` | 🔄 Fixing |
| 4 | Datetime parsing timezone bug | `commands/status.py:48,60` | 🔄 Fixing |

---

## Task Tracker

| Task | Phase | Priority | Status |
|---|---|---|---|
| MemoryClient Python API | 1 | 🔴 Critical | ⬜ Not started |
| JSON output for all commands | 1 | 🔴 Critical | ⬜ Not started |
| Confidence + provenance columns | 1 | 🟡 High | ⬜ Not started |
| Update AGENTS.md with Python API | 1 | 🟡 High | ⬜ Not started |
| Hook system (config.yaml) | 2 | 🔴 Critical | ⬜ Not started |
| `memory suggest --from-pwd` | 2 | 🟡 High | ⬜ Not started |
| Executable SKILL.md templates | 2 | 🟡 Medium | ⬜ Not started |
| Integration tests for agent workflows | 2 | 🟡 Medium | ⬜ Not started |
| Native Hermes MCP integration | 3 | 🔴 Critical | ⬜ Not started |
| Memory verification loop | 3 | 🟡 Medium | ⬜ Not started |
| Session continuity protocol | 3 | 🟡 Medium | ⬜ Not started |
| Ollama fallback for consolidation | 3 | 🟡 Medium | ⬜ Not started |
| Cross-project memory queries | 3 | 🟡 Low | ⬜ Not started |
| Fix topicify vector logic bug | — | 🔴 High | 🔄 In progress |
| Fix consolidation subprocess timeout | — | 🔴 High | 🔄 In progress |
| Fix FTS5 over-sanitization | — | 🟡 Medium | 🔄 In progress |
| Fix datetime parsing timezone | — | 🟡 Medium | 🔄 In progress |

---

## Notes

- All Phase 1 tasks should be completed before Phase 2 begins
- Phase 3 tasks can be done in parallel with other work
- SKILL.md files should be updated whenever a Phase task changes agent behavior
- After each phase, update this document with completion dates