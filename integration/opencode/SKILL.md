---
name: cheapskate-memory
description: "Auto-drive Cheapskate Agent Memory (CAM) for persistent project context"
version: 1.0.0
author: CAM Integration
license: MIT
platforms: [linux, macos, windows]
metadata:
  opencode:
    tags: [memory, cheapskate, persistence, project-context, agentic-memory]
---

# Cheapskate Agent Memory — CAM Skill for OpenCode

Use this skill to persist project context across coding sessions. CAM is a zero-cost, fully-local memory system that stores facts discovered during work — no cloud, no API fees.

**Install CAM first:**
```bash
pip install cheapskate-agent-memory  # or: pip install -e ~/Cheapskate-Agent-Memory
memory init
```

---

## Trigger Conditions

Activate this skill when:
- Starting work on a project (search for context first)
- User says "remember..." or "don't forget..."
- About to modify project architecture or setup
- Debugging (check for known issues/patterns first)
- Completing a feature (consolidate memories)

---

## Core Commands

### Adding Memories

```bash
# Basic syntax
memory add "fact content" --project PROJECT_NAME --tags tag1,tag2 --source agent

# Common patterns:
memory add "Backend runs on port 4000" --project myapp --tags ports,dev
memory add "Project uses pnpm, not npm" --project myapp --tags conventions
memory add "Docker service 'db' is PostgreSQL on 5432" --project myapp --tags infrastructure
memory add "Tests: pnpm test:unit --coverage" --project myapp --tags testing
memory add "EADDRINUSE on port 4000 means another server is running" --project myapp --tags errors
```

### Searching

```bash
# Load context at session start
memory search "context about this project" --project myapp

# Before major changes
memory search "architecture" --project myapp
memory search "database" --project myapp
memory search "auth" --project myapp

# Debugging
memory search "error" --project myapp
memory search "port" --project myapp

# Cross-project
memory search "docker" --all-projects
```

### Topic Management

```bash
# Group related memories
memory topicify --project myapp --auto

# Manual topic
memory topic create debugging --project myapp --memory-ids 1,2,3
memory topic list --project myapp
```

### Consolidation

```bash
# End of day synthesis
memory consolidate --project myapp

# Stats
memory status
memory stats --project myapp
```

---

## Heuristics — When to Add Memories

**ADD when you discover:**

| Type | Example |
|------|---------|
| Ports | "Backend on 4000, frontend on 3000" |
| Errors | "EACCES on 80 = another process" |
| Commands | Custom scripts, test commands |
| Env vars | DATABASE_URL, API_SECRET |
| Package managers | pnpm, bun (not npm) |
| Services | Docker names, database names |
| Architecture | "Event sourcing for orders" |
| API patterns | "POST returns 201 with user object" |

**SKIP:**
- Generic syntax, stdlib
- Standard patterns (npm install)
- Ephemeral session info
- User preferences

---

## Memory vs Project Config

**Memory**: Discovered facts (port numbers, service names, error patterns)
**CLAUDE.md / config**: User decisions (use pnpm, prefer functional components)

**Rule**: User decided → config. Agent discovered → memory.

---

## Session Workflow

```
1. START: memory search "context" --project myapp
2. WORK:  Add memories as you discover facts
3. USER:  "remember..." → add with --source user
4. END:   memory topicify --project myapp --auto
5. DAILY: memory consolidate --project myapp
```

---

## Example Memory Entries

```bash
# Infrastructure
memory add "PostgreSQL on port 5432, accessed via DATABASE_URL" --project myapp --tags infrastructure,database

# Conventions
memory add "Use pnpm, not npm or yarn" --project myapp --tags conventions
memory add "Test files: *.test.ts, run with pnpm test:unit" --project myapp --tags testing

# Architecture
memory add "Auth via JWT in Authorization header" --project myapp --tags security,api
memory add "API returns 422 on validation errors" --project myapp --tags api,errors

# Debugging
memory add "EADDRINUSE on ports: another dev server running, kill with lsof -i :PORT" --project myapp --tags debugging
```

---

## Configuration

`~/.memory/config.yaml`:
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

## Tips

1. **Quality over quantity** — Specific facts > generic statements
2. **Include context** — "Port 8080" vs "Backend on 8080, frontend on 3000"
3. **Use tags** — Makes search faster, topicify smarter
4. **Search first** — Before debugging, check what's already known
5. **Topicify** — Run after sessions to organize memories
6. **Consolidate** — Daily synthesis keeps memory fresh

---

## Verification

```bash
# Check recent memories
memory list --project myapp --limit 5

# Verify search
memory search "port" --project myapp

# Check topics
memory topic list --project myapp

# Status
memory status
```

---

*Part of [Cheapskate Agent Memory](https://github.com/canh0chua/Cheapskate-Agent-Memory)*