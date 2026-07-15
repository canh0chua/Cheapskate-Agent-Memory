# Cheapskate Agent Memory — Agent Awareness Guide

**CAM is a zero-cost, fully-local memory system for coding agents** — no cloud, no API fees, built on SQLite + FTS5 + HRR vector search.

This guide teaches ANY coding agent (Claude Code, Hermes, OpenCode, Codex, etc.) to drive CAM automatically, without needing native integration.

---

## What CAM Does

CAM stores project-derived facts discovered during coding sessions:
- Port numbers, error codes, service names
- Non-standard commands and conventions
- Environment variables and configuration
- Architecture decisions and patterns

**Three capture modes:**
1. **User-driven**: User says "remember that..."
2. **Agent auto-capture**: Agent fires heuristics when discovering facts
3. **Silent config-driven**: `~/.memory/config.yaml` auto-capture settings

---

## When to Call `memory add`

Fire these heuristics automatically when you discover worth-knowing facts:

### Add to Memory (Worth Remembering)
- **Port numbers**: "Backend runs on port 4000"
- **Error + fix pairs**: "EACCES on port 80 means another process is using it"
- **Non-standard commands**: Not `npm ci`, but `pnpm install` or custom scripts
- **Environment variables**: `DATABASE_URL`, `API_KEY`, custom vars
- **Package managers**: pnpm, bun, not npm
- **Test framework patterns**: `pytest -n auto`, custom test commands
- **Service names**: Docker Compose service names, database names
- **Architecture decisions**: "We use event sourcing for orders"
- **API response shapes**: "POST /api/users returns 201 with user object"
- **Config structures**: Auth middleware config, feature flags

### NOT Worth Remembering
- Generic programming facts (syntax, stdlib)
- Already-known patterns (`npm install`, standard `pytest`)
- Ephemeral session info (file paths, cursor position)
- User preferences (those go in CLAUDE.md)

### Heuristic Examples
```bash
# You ran: docker compose ps
# Discovered: PostgreSQL on port 5432, Redis on 6379
memory add "PostgreSQL on port 5432, Redis on port 6379" --project myapp --tags infra,database

# You ran: docker compose config
# Discovered: service named 'db' not 'postgres'
memory add "Docker service 'db' is the PostgreSQL container" --project myapp --tags infra

# You hit an error: EADDRINUSE
# Fixed it by killing the process on port 3000
memory add "EADDRINUSE on port 3000: another dev server already running" --project myapp --tags errors

# You noticed: package manager is pnpm
memory add "Project uses pnpm, not npm or yarn" --project myapp --tags conventions

# You read: .env.example
# Discovered: required env vars DATABASE_URL, REDIS_URL, API_SECRET
memory add "Required env vars: DATABASE_URL, REDIS_URL, API_SECRET" --project myapp --tags config,env

# You discovered: custom test command
memory add "Tests run with: pnpm test:unit --coverage" --project myapp --tags testing,commands
```

---

## When to Call `memory search`

### Session Start
At the beginning of every coding session, search for context:
```bash
memory search "context about this project" --project myapp
memory search "port" --project myapp --all-projects
memory search "error" --project myapp --all-projects
```

This loads relevant facts before you start work.

### Before Major Changes
Before refactoring or architecture changes:
```bash
memory search "architecture" --project myapp
memory search "database schema" --project myapp
memory search "auth" --project myapp
```

### Debugging
When investigating issues:
```bash
memory search "port" --project myapp
memory search "error" --project myapp
memory search "docker" --project myapp
```

---

## When to Call `memory topicify`

After meaningful work sessions (when you added 5+ new memories):
```bash
memory topicify --project myapp --auto
```

This auto-groups related memories into topic files. Run this:
- After completing a feature
- After fixing multiple bugs
- Before ending a long session
- When memories feel disorganized

---

## When to Call `memory consolidate`

### End of Day
```bash
memory consolidate --project myapp
```

This runs Dreams-style synthesis:
- Summarizes new memories per topic
- Resolves contradictions
- Updates topic files
- Rewrites MEMORY.md index (25KB cap)
- Syncs rules to CLAUDE.md files

### After Many New Memories
When you have 50+ new memories since last consolidate:
```bash
memory consolidate --project myapp
```

---

## How to Write Good Memory Content

### Be Specific
- BAD: "uses a database"
- GOOD: "PostgreSQL on port 5432, accessed via DATABASE_URL env var"

- BAD: "has tests"
- GOOD: "Tests run with pnpm test:unit --coverage, requires DB_CONNECTION"

### Be Factual
- BAD: "probably uses Redis for caching"
- GOOD: "Redis on port 6379, used for session storage and rate limiting"

### Include Context
- BAD: "port 8080"
- GOOD: "Backend dev server runs on port 8080 (API), frontend on 3000"

### Use Tags
```bash
memory add "PostgreSQL on port 5432" --tags infrastructure,database,ports
```

---

## Memory vs CLAUDE.md Boundary

| Location | What Goes There |
|----------|-----------------|
| **Memory** | Discovered facts — things the agent learned by inspecting the project |
| **CLAUDE.md** | User decisions — things the user explicitly wants enforced |

### Examples

**Memory (discovered):**
- "Port 4000 is the backend port"
- "Docker service named 'db' is PostgreSQL"
- "API returns 422 on validation errors"

**CLAUDE.md (decisions):**
- "Always use pnpm, never npm"
- "Prefer functional components"
- "No console.log in production code"

**Rule of thumb:**
- If the **user decided** it → CLAUDE.md
- If the **agent discovered** it → memory

---

## Agent Session Flow

```
User starts coding session
  │
  ├─→ Agent calls: memory search "context"
  │           ← returns MEMORY.md + relevant facts
  │
  ├─→ Agent works, auto-captures when heuristics fire
  │           memory add "PostgreSQL on port 5432"
  │
  ├─→ User can say "remember..." at any time
  │
  └─→ Session ends
              │
              ▼
        Cron fires (nightly)
              │
  ├─→ memory consolidate
  │   • LLM reads new memories
  │   • Updates topic files
  │   • Rewrites MEMORY.md
  │   • Syncs rules → CLAUDE.md
  │
  └─→ Next session: loads MEMORY.md + topics
```

---

## Tips for Agents

1. **Be Proactive**: Don't wait to be asked. Fire heuristics when you discover facts.
2. **Be Specific**: Generic memories are noise. Include context.
3. **Use Tags**: Tags make retrieval faster and topicify more accurate.
4. **Respect the Boundary**: User decisions → CLAUDE.md, discovered facts → memory.
5. **Consolidate Regularly**: Raw memories accumulate. Consolidate to keep things organized.
6. **Search Before Acting**: A quick `memory search` saves debugging time.
7. **Clean Up**: Run `memory prune --dry-run` occasionally to keep memory lean.

---

## Essential Commands Reference

```bash
# Initialize (first time)
memory init

# Add a fact
memory add "fact content" --project myapp --tags tag1,tag2 --source agent

# Search
memory search "query" --project myapp --all-projects

# List
memory list --project myapp --limit 20

# Topic management
memory topicify --project myapp --auto
memory topic create debugging --project myapp --memory-ids 1,2,3

# Consolidation
memory consolidate --project myapp

# Status & Stats
memory status
memory stats --project myapp

# Pruning
memory prune --project myapp --dry-run
```

---

## Configuration

Config file: `~/.memory/config.yaml`

```yaml
capture:
  max_per_session: 50
  tags_whitelist: [db, infra, api, errors, dev]

forgetting:
  decay_days: 90
  max_age_days: 365
  include_contradicted: false
  soft_delete: true

consolidate:
  schedule: "0 2 * * *"   # cron: 2am daily
  trigger_threshold: 100
```

---

## SKILL Templates

For programmatic skill loading, see [skill-template.md](./skill-template.md). It contains a machine-readable YAML definition that agents can parse to generate exact CLI commands, understand decision trees, and auto-detect trigger conditions.

---

## Integration Status

CAM currently works as a **CLI-orchestrated tool**. Agents invoke it via `subprocess`. The roadmap (see `docs/agent-review-3.md`) plans to add a Python API for direct import.

### Current Integration Method (CLI)
```bash
memory add "fact" --project myapp
memory search "query" --project myapp
```

### Planned Integration Method (Python API — coming soon)
```python
from cheapskate import MemoryClient

mem = MemoryClient()
mem.add("fact", project="myapp")
results = mem.search("query", project="myapp")
```

### Planned: JSON Output (coming soon)
```bash
memory search "port" --project myapp --json
# {"results": [...], "count": 5, "query": "port", "project": "myapp"}
```

---

## Example Agent Interactions

### Example 1: New Project Setup
```
Agent: Let me check the project memory first.
→ memory search "context" --project myapp

Agent: No existing memories. Let me explore.
→ Reads package.json, docker-compose.yml, .env.example

Agent: I see this project uses pnpm, Docker with a 'db' service for PostgreSQL on 5432, and has custom test commands. Let me save these facts.
→ memory add "Project uses pnpm, not npm or yarn" --project myapp --tags conventions
→ memory add "Docker service 'db' is PostgreSQL on port 5432" --project myapp --tags infrastructure
→ memory add "Tests: pnpm test:unit --coverage" --project myapp --tags testing
```

### Example 2: Debugging Session
```
Agent: Getting EADDRINUSE error. Let me check memory.
→ memory search "port" --project myapp

Agent: Memory shows backend runs on 4000. Let me check what's using it.
→ lsof -i :4000

Agent: Another process. User is already running the dev server.
```

### Example 3: End of Session
```
Agent: Done for today. Let me consolidate memories.
→ memory topicify --project myapp --auto
→ memory consolidate --project myapp
```