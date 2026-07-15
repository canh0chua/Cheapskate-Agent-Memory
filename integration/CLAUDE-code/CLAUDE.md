# Cheapskate Agent Memory — CAM Integration

I use **Cheapskate Agent Memory (CAM)** to store project facts discovered during work sessions — so we don't repeat the same discoveries.

**Setup (first time):**
```bash
pip install -e ~/Cheapskate-Agent-Memory  # or: pip install cheapskate-agent-memory
memory init
```

---

## Session Workflow

Run at the **start of every session**, then throughout:

```
Session start
  └─→ memory search "context" --project <project>
  └─→ memory search "port" --project <project> --all-projects
  └─→ memory search "error" --project <project> --all-projects
        ↓
During work: capture worth-knowing facts (see below)
        ↓
End of session (5+ new memories):
  └─→ memory topicify --project <project> --auto
Nightly (cron):
  └─→ memory consolidate --project <project>
```

---

## When to Add a Memory

**Fire `memory add` when you discover:**

| Trigger | Example |
|---|---|
| Port numbers | "Backend on 4000, PostgreSQL on 5432" |
| Error + fix pairs | "EADDRINUSE on 4000 = server already running" |
| Non-standard commands | "Use `pnpm dev`, not `npm run dev`" |
| Env vars that matter | "Auth requires API_SECRET in .env" |
| Docker service names | "Service 'db' is PostgreSQL" |
| Architecture decisions | "Event sourcing for the orders module" |
| Custom test commands | "Run tests: pnpm test:unit --coverage" |

**Do NOT add:**
- Generic syntax / stdlib facts
- Ephemeral session info (file paths, cursor position)
- User preferences (those belong in CLAUDE.md — see boundary below)

**Format:** Be specific. ❌ "uses a database" → ✅ "PostgreSQL on 5432 via DATABASE_URL"

```bash
memory add "Backend runs on port 4000" --project myapp --tags ports
memory add "Docker service 'db' is PostgreSQL on 5432" --project myapp --tags infrastructure
memory add "EADDRINUSE on 4000 = another dev server running" --project myapp --tags errors
memory add "Tests: pnpm test:unit --coverage" --project myapp --tags testing
```

---

## When to Search Memories

- **Session start** — load context before working
- **Before refactoring / architecture changes**
- **Debugging** — search `error`, `docker`, `port` first

```bash
memory search "context" --project myapp
memory search "architecture" --project myapp
memory search "error" --project myapp
```

---

## Memory vs CLAUDE.md Boundary

| Memory (discovered) | CLAUDE.md (enforced) |
|---|---|
| "Port 4000 is the backend" | "Always use pnpm, never npm" |
| "Docker service 'db' = PostgreSQL" | "Prefer functional components" |
| "API returns 422 on validation errors" | "No console.log in production" |

**Rule:** user *decided* → CLAUDE.md. Agent *discovered* → memory.

---

## Quick Reference

```bash
memory add "fact" --project myapp --tags tag1,tag2   # capture
memory search "query" --project myapp                 # retrieve
memory list --project myapp --limit 20                # list
memory topicify --project myapp --auto               # group
memory consolidate --project myapp                   # synthesize (nightly)
memory status && memory stats --project myapp         # stats
memory prune --project myapp --dry-run                # cleanup
```

---

*Part of [Cheapskate Agent Memory](https://github.com/canh0chua/Cheapskate-Agent-Memory)*