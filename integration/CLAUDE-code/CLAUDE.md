# CAM Integration for Claude Code

**Copy this to:**
- Global: `~/.claude/CLAUDE.md`
- Project: `./CLAUDE.md` (git-tracked, team-shared)
- Local: `./.claude/CLAUDE.local.md` (gitignored, personal)

---

# Cheapskate Agent Memory — CAM Integration

I use **Cheapskate Agent Memory (CAM)** for persistent, searchable project context. CAM is a zero-cost, fully-local memory system — no cloud, no API fees, built on SQLite + FTS5.

**First time setup:**
```bash
pip install cheapskate-agent-memory  # or: pip install -e ~/Cheapskate-Agent-Memory
memory init
```

---

## Essential CAM Commands

```bash
# Add a fact (auto-capture when you discover worth-knowing things)
memory add "fact content" --project myapp --tags tag1,tag2 --source agent

# Search (do this at session start and before major changes)
memory search "query" --project myapp --all-projects

# List recent memories
memory list --project myapp --limit 20

# Topic management (group related memories)
memory topicify --project myapp --auto

# Consolidation (Dreams-style synthesis)
memory consolidate --project myapp

# Status
memory status
memory stats --project myapp
```

---

## When to Add Memories (Heuristics)

**✅ ADD to memory when you discover:**
- Port numbers (e.g., "backend runs on 4000")
- Error codes + fix pairs (e.g., "EACCES on port 80 = another process")
- Non-standard commands (not `npm ci`, but `pnpm install`, custom scripts)
- Environment variables that matter (`DATABASE_URL`, custom vars)
- Package managers (pnpm, bun, not npm)
- Test framework patterns (`pytest -n auto`, custom commands)
- Docker Compose service names
- Architecture decisions made during session
- API response shapes and error codes

**❌ DON'T add:**
- Generic programming facts (syntax, stdlib)
- Already-known patterns (npm install, standard pytest)
- Ephemeral session info (file paths, cursor position)
- User preferences (those go in CLAUDE.md)

---

## When to Search Memories

**Session Start:**
```bash
memory search "context about this project" --project myapp
memory search "port" --project myapp --all-projects
```

**Before Major Changes:**
```bash
memory search "architecture" --project myapp
memory search "database schema" --project myapp
memory search "auth" --project myapp
```

**Debugging:**
```bash
memory search "error" --project myapp
memory search "docker" --project myapp
```

---

## Memory vs CLAUDE.md Boundary

| Location | What Goes There |
|----------|-----------------|
| **Memory** | Discovered facts — things I learned by inspecting the project |
| **CLAUDE.md** | User decisions — things the user explicitly wants enforced |

**Examples:**
- Memory: "Port 4000 is the backend port"
- Memory: "Docker service named 'db' is PostgreSQL"
- Memory: "API returns 422 on validation errors"
- CLAUDE.md: "Always use pnpm, never npm"
- CLAUDE.md: "Prefer functional components"
- CLAUDE.md: "No console.log in production"

---

## Example Interactions

### Adding Memories
```bash
memory add "Project uses pnpm, not npm or yarn" --project myapp --tags conventions
memory add "Docker service 'db' is PostgreSQL on port 5432" --project myapp --tags infrastructure
memory add "Tests: pnpm test:unit --coverage" --project myapp --tags testing
memory add "Backend runs on port 4000" --project myapp --tags ports,dev
memory add "EADDRINUSE on port 4000: dev server already running" --project myapp --tags errors,debugging
```

### Session Flow
1. **Start**: `memory search "context" --project myapp`
2. **Work**: Add memories when heuristics fire
3. **End**: `memory topicify --project myapp --auto`
4. **Nightly**: `memory consolidate --project myapp` (via cron)

---

## Quick Commands Reference

| Task | Command |
|------|---------|
| Add fact | `memory add "fact" --project myapp --tags tags` |
| Search | `memory search "query" --project myapp` |
| List | `memory list --project myapp --limit 20` |
| Topicify | `memory topicify --project myapp --auto` |
| Consolidate | `memory consolidate --project myapp` |
| Status | `memory status` |

---

## Memory Source Types

When adding memories, use `--source` to indicate origin:
- `--source agent` — Auto-captured by heuristics (default)
- `--source user` — User explicitly requested ("remember that...")
- `--source extracted` — Pulled from code/config parsing

Use `--source user` when the user says "remember..." and I'll add it as a user preference (which may belong in CLAUDE.md).

---

## Tips

1. **Be specific**: ❌ "uses database" → ✅ "PostgreSQL on port 5432"
2. **Include context**: ❌ "port 8080" → ✅ "Backend on 8080, frontend on 3000"
3. **Use tags**: Makes retrieval faster, topicify more accurate
4. **Search before acting**: A quick memory search saves debugging time
5. **Topicify after sessions**: `memory topicify --auto` groups related memories
6. **Consolidate daily**: `memory consolidate` runs Dreams-style synthesis

---

*This integration is part of [Cheapskate Agent Memory](https://github.com/canh0chua/Cheapskate-Agent-Memory)*