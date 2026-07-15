---
name: cheapskate-memory
description: "Auto-drive Cheapskate Agent Memory (CAM) for persistent project context"
version: 1.0.0
author: CAM Integration
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [memory, cheapskate, persistence, project-context, agentic-memory]
    homepage: https://github.com/canh0chua/Cheapskate-Agent-Memory
---

# Cheapskate Agent Memory — CAM Skill for Hermes

Use this skill whenever you need to persist project context across sessions. CAM is a zero-cost, fully-local memory system that stores facts discovered during coding work.

**Install CAM first:**
```bash
pip install cheapskate-agent-memory  # or: pip install -e ~/Cheapskate-Agent-Memory
memory init
```

---

## Trigger Conditions

Load this skill automatically when:
- Starting a new coding session on any project
- User says "remember that..." or "don't forget..."
- User asks about project architecture, setup, or conventions
- You're about to make significant changes to a project
- Debugging issues (check memory for known patterns first)

Load manually with: `/skill cheapskate-memory`

---

## Core Commands

### Adding Memories

```bash
# Basic add
memory add "fact content" --project myapp --tags tag1,tag2 --source agent

# Common examples:
memory add "Backend runs on port 4000" --project myapp --tags ports,dev
memory add "Project uses pnpm, not npm" --project myapp --tags conventions
memory add "Docker service 'db' is PostgreSQL on 5432" --project myapp --tags infrastructure
memory add "Tests: pnpm test:unit --coverage" --project myapp --tags testing
memory add "EADDRINUSE on port 4000: another dev server running" --project myapp --tags errors,debugging
```

### Searching Memories

```bash
# Session start - load context
memory search "context about this project" --project myapp

# Before major changes
memory search "architecture" --project myapp
memory search "database" --project myapp
memory search "auth" --project myapp

# Debugging
memory search "error" --project myapp
memory search "port" --project myapp

# Cross-project search
memory search "docker" --all-projects
```

### Topic Management

```bash
# Auto-group related memories (after adding 5+ memories)
memory topicify --project myapp --auto

# Create topic manually
memory topic create debugging --project myapp --memory-ids 1,2,3
memory topic list --project myapp
```

### Consolidation

```bash
# End of day - Dreams-style synthesis
memory consolidate --project myapp

# Status & stats
memory status
memory stats --project myapp
```

---

## When to Fire Heuristics

**ADD memories when you discover:**

| Category | Example |
|----------|---------|
| Ports | "Backend on 4000, frontend on 3000" |
| Errors | "EACCES on 80 = another process" |
| Commands | Custom test/build/deploy commands |
| Env vars | DATABASE_URL, API_SECRET, custom vars |
| Package managers | pnpm, bun, not npm |
| Services | Docker service names, database names |
| Architecture | Event sourcing, microservices pattern |
| API shapes | Response formats, error codes |
| Config | Auth middleware, feature flags |

**DO NOT add:**
- Generic programming facts (syntax, stdlib)
- Already-known patterns (npm install, pytest)
- Ephemeral info (file paths, cursor)
- User preferences (those go in CLAUDE.md)

---

## Memory vs CLAUDE.md

| Memory | CLAUDE.md |
|--------|-----------|
| Discovered facts | User decisions |
| "Port 4000" | "Always use pnpm" |
| "Service 'db'" | "Prefer functional components" |
| "422 = validation error" | "No console.log in prod" |

**Rule**: User decided it → CLAUDE.md. Agent discovered it → memory.

---

## Session Flow Example

```
1. Start session:
   memory search "context" --project myapp

2. Work, add memories when heuristics fire:
   memory add "PostgreSQL on 5432" --project myapp --tags db
   memory add "Tests use pnpm test:unit" --project myapp --tags testing

3. User says "remember we use pnpm":
   memory add "User preference: always use pnpm" --project myapp --source user
   → Also add to CLAUDE.md since it's a user decision

4. End of session:
   memory topicify --project myapp --auto

5. Nightly (via cron):
   memory consolidate --project myapp
```

---

## Integration with Hermes Memory

CAM complements Hermes built-in memory:
- **Hermes memory**: User profile, preferences, conversation context
- **CAM**: Project-specific facts discovered during coding

Use CAM for persistent project context; Hermes memory for user preferences and cross-project context.

---

## Configuration

Edit `~/.memory/config.yaml`:
```yaml
capture:
  max_per_session: 50
  tags_whitelist: [db, infra, api, errors, dev]

forgetting:
  decay_days: 90
  max_age_days: 365

consolidate:
  schedule: "0 2 * * *"
  trigger_threshold: 100
```

---

## Pitfalls

1. **Don't flood**: Max 50 memories per session (configurable). Quality > quantity.
2. **Be specific**: ❌ "uses database" → ✅ "PostgreSQL on 5432"
3. **Include context**: ❌ "port 8080" → ✅ "Backend on 8080, frontend on 3000"
4. **Use tags**: Makes retrieval 10x faster
5. **Consolidate**: Raw memories accumulate. Run `memory consolidate` regularly.
6. **Source matters**: Use `--source user` for user preferences (they may belong in CLAUDE.md too)

---

## Verification Steps

1. **After adding memories:**
   ```bash
   memory list --project myapp --limit 5
   # Should show recent memories with correct tags
   ```

2. **After topicify:**
   ```bash
   memory topic list --project myapp
   # Should show created topics
   ```

3. **After consolidate:**
   ```bash
   memory status
   # Should show last_consolidate timestamp updated
   ```

4. **Verify search works:**
   ```bash
   memory search "port" --project myapp
   # Should return relevant memories
   ```

---

## Skill Metadata

| Field | Value |
|-------|-------|
| Name | cheapskate-memory |
| Version | 1.0.0 |
| Category | memory |
| Platforms | linux, macos, windows |
| Dependencies | cheapskate-agent-memory CLI |

---

*Part of [Cheapskate Agent Memory](https://github.com/canh0chua/Cheapskate-Agent-Memory) integration*