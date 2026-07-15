# Cheapskate Agent Memory — SKILL Template

> Machine-readable skill template for coding agents to parse and execute CAM workflows.

<!--
SKILL TEMPLATE FORMAT v1.0
This file defines executable workflows for coding agents.
Agents should parse YAML frontmatter + markdown to extract:
- Trigger conditions (when this skill activates)
- Workflow steps (numbered with exact CLI commands)
- Decision trees (if X, then Y)
- Examples and outputs
-->

```yaml
---
skill: cheapskate-agent-memory
version: "1.0"
description: "Zero-cost, fully-local memory system for coding agents"
trigger:
  keywords: [memory, remember, recall, context, facts, knowledge]
  events: [session_start, debugging, architecture_review]
  patterns:
    - "remember that*"
    - "what do you know*"
    - "search memory*"
    - "memory suggest*"
actions:
  - name: init
    description: Initialize memory database
    command: memory init
    flags:
      - name: --path
        type: Path
        default: ~/.memory
        description: Memory directory path
      - name: --force
        type: boolean
        default: false
        description: Force reinitialization
    example: memory init --path ~/.memory
    output: "Creates memory.db and config.yaml"

  - name: add
    description: Add a memory entry
    command: memory add "content" [flags]
    flags:
      - name: --project, -p
        type: string
        default: default
        description: Project name
      - name: --tags, -t
        type: string
        description: Comma-separated tags
      - name: --source, -s
        type: enum
        values: [user, agent, extracted, llm_consolidate]
        default: agent
        description: Memory source
    example: memory add "PostgreSQL on port 5432" -p myapp -t infra,database
    output: "Returns memory ID on success"

  - name: search
    description: Search memories
    command: memory search "query" [flags]
    flags:
      - name: --project, -p
        type: string
        description: Filter by project
      - name: --all-projects
        type: boolean
        default: false
        description: Search all projects
      - name: --json, -j
        type: boolean
        default: false
        description: JSON output
      - name: --limit, -n
        type: int
        default: 20
        description: Result limit
    example: memory search "port" -p myapp --json
    output: '{"results": [...], "count": N, "query": "port"}'

  - name: list
    description: List memories
    command: memory list [flags]
    flags:
      - name: --project, -p
        type: string
        description: Filter by project
      - name: --all-projects
        type: boolean
        default: false
        description: List all projects
      - name: --json, -j
        type: boolean
        default: false
        description: JSON output
      - name: --limit, -n
        type: int
        default: 100
        description: Result limit
    example: memory list -p myapp --json
    output: '{"memories": [...], "count": N, "total": M}'

  - name: stats
    description: Get memory statistics
    command: memory stats [flags]
    flags:
      - name: --project, -p
        type: string
        description: Filter by project
      - name: --json, -j
        type: boolean
        default: false
        description: JSON output
    example: memory stats -p myapp --json
    output: '{"memories": N, "topics": M, "sources": {...}}'

  - name: suggest
    description: Auto-suggest relevant memories from current project
    command: memory suggest [flags]
    flags:
      - name: --project, -p
        type: string
        description: Project name (auto-detected if omitted)
      - name: --from-pwd
        type: boolean
        default: true
        description: Auto-detect project from current directory
      - name: --json, -j
        type: boolean
        default: false
        description: JSON output
      - name: --limit, -n
        type: int
        default: 5
        description: Max suggestions
    example: memory suggest --from-pwd --json
    output: '{"project": "myapp", "count": 3, "suggestions": [...]}'

  - name: topicify
    description: Auto-group memories into topics
    command: memory topicify --project PROJECT [flags]
    flags:
      - name: --project, -p
        type: string
        required: true
        description: Project name
      - name: --auto
        type: boolean
        default: false
        description: Use auto mode (tags + similarity)
      - name: --group-by
        type: enum
        values: [tags, vector, keywords, auto]
        default: tags
        description: Grouping strategy
    example: memory topicify -p myapp --auto
    output: "Creates topic files for grouped memories"

  - name: consolidate
    description: Synthesize memories using LLM (requires Claude Code CLI)
    command: memory consolidate --project PROJECT
    flags:
      - name: --project, -p
        type: string
        required: true
        description: Project name
    example: memory consolidate -p myapp
    output: "Updates topic files, rewrites MEMORY.md"

  - name: status
    description: Show memory system status
    command: memory status [flags]
    flags:
      - name: --json, -j
        type: boolean
        default: false
        description: JSON output
    example: memory status --json
    output: '{"initialized": true, "memory_dir": "...", "stats": {...}}'

decision_trees:
  - trigger: session_start
    description: What to do at session start
    steps:
      - if: first time using CAM
        then:
          - run: memory init
          - run: memory add "Initial setup" -s user
      - else:
          - run: memory suggest --from-pwd
          - run: memory search "context" -p PROJECT

  - trigger: discovered_fact
    description: When discovering worth-knowing facts
    steps:
      - if: fact involves ports, errors, commands, configs, conventions
        then:
          - run: memory add "FACT_CONTENT" -p PROJECT -t TAG
      - else:
          - skip: Generic programming facts

  - trigger: debugging
    description: When debugging issues
    steps:
      - run: memory search "error" -p PROJECT
      - run: memory search "port" -p PROJECT
      - run: memory search "config" -p PROJECT

confidence_defaults:
  user: 1.0
  agent: 0.7
  extracted: 0.5
  llm_consolidate: 0.6

source_keywords:
  user: [remember, tell me, note that]
  agent: [discovered, found, noticed, detected]
  extracted: [scanned, parsed, read from]
  llm_consolidate: [consolidated, synthesized]
```

---

## Workflow Examples

### Session Start Workflow
```bash
# 1. Initialize (first time only)
memory init

# 2. Get relevant memories from current project
memory suggest --from-pwd

# 3. Search for specific context if needed
memory search "auth" -p myapp
```

### Fact Discovery Workflow
```bash
# When you discover a worth-knowing fact:
memory add "PostgreSQL on port 5432, Redis on 6379" \
  -p myapp \
  -t infra,database \
  -s agent

# When you hit and fix an error:
memory add "EADDRINUSE on port 3000: another dev server running" \
  -p myapp \
  -t errors \
  -s agent
```

### JSON Output Workflow
```bash
# Get memories as JSON for programmatic use
memory list -p myapp --json
# {"memories": [...], "count": 5, "total": 10}

memory stats -p myapp --json
# {"memories": 10, "topics": 3, "rules": 2, "sources": {...}}

memory search "port" -p myapp --json
# {"results": [...], "count": 3, "query": "port", "project": "myapp"}

memory suggest --from-pwd --json
# {"project": "myapp", "count": 5, "suggestions": [...]}
```

### Topic Management Workflow
```bash
# Auto-group memories into topics
memory topicify -p myapp --auto

# Create topic manually
memory topic create debugging -p myapp -m 1,2,3

# List topics
memory topic list -p myapp

# Delete topic
memory topic delete old-topic -p myapp
```

---

## Hooks Configuration

CAM supports hooks defined in `~/.memory/config.yaml`:

```yaml
hooks:
  on_session_start:
    - command: echo "Session started: {project}"
      output: visible
  on_error:
    - command: memory add "Error: {error}" -p {project} -t errors -s agent
      output: silent
  on_file_edit:
    - command: memory add "Modified: {filename}" -p {project} -t code
      output: silent
  on_session_end:
    - command: memory consolidate -p {project}
      output: silent
```

Hook placeholders: `{project}`, `{error}`, `{filename}`, `{context}`

---

## Python API

```python
from cheapskate import MemoryClient, run_hooks

# Initialize
mem = MemoryClient()
mem.init()

# Add memories
mem.add("PostgreSQL on port 5432", project="myapp", tags=["infra"])

# Search
results = mem.search("port", project="myapp")

# List with JSON output
memories = mem.list(project="myapp")
stats = mem.stats(project="myapp")

# Hooks (run on events)
run_hooks('on_session_start', project='myapp')
run_hooks('on_file_edit', project='myapp', context={'filename': 'main.py'})
```

---

*This template is machine-parseable. Agents should extract action definitions from the YAML frontmatter and use them to generate exact CLI commands.*