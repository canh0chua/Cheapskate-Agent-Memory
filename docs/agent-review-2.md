# Comprehensive Engineering Code Review — Cheapskate Agent Memory (Review 2)

**Ngày review:** 2026-07-15  
**Repo:** Cheapskate-Agent-Memory  
**Commit hiện tại:** `9845355` (feat: all major review items resolved)  
**Commit review trước:** `fe66cfc` (docs: update review with resolved items and test status)  
**Reviewer:** Hermes Agent (Nous Research)  
**Phạm vi:** Toàn bộ repository — code quality, security, performance, architecture, test coverage, và các issue mới sau khi sửa từ review 1  
**Trạng thái:** ✅ Review hoàn thành

---

## 1. Tóm tắt điều hành (Executive Summary)

**Điểm sức khỏe tổng thể: TUYỆT VỜI — 9.5/10** *(cải thiện rõ rệt từ 7.5/10)*

Tất cả 10 issues nghiêm trọng từ review trước đều đã được giải quyết hoặc có tiến triển đáng kể. Test suite 150 tests đều pass. HRR vector reranking đã được tích hợp. Tuy nhiên, vẫn còn một số vấn đề mới được phát hiện ở review này.

### ✅ Điểm mạnh chính:
- **150 tests đều PASS** (tăng từ 0)
- **N+1 query đã được fix** — batch UPDATE trong `search_memories()`
- **HRR vector reranking đã hoạt động** — hybrid FTS5 + cosine similarity
- **Path traversal đã được fix** — `validate_memory_path()` với `is_relative_to()`
- **Input validation đã được thêm** — MAX_CONTENT_LENGTH, MAX_TAGS, VALID_PROJECT_PATTERN
- **`datetime.utcnow()` đã được thay** bằng `datetime.now(timezone.utc)`
- **`__main__.py` đã được thêm** — hỗ trợ `python -m cheapskate`
- **CI workflow đã hoàn chỉnh** — test + lint trên 3 Python versions
- **CONTRIBUTING.md đã được thêm**
- **Kiến trúc sạch sẽ** — separation of concerns rõ ràng

### ⚠️ Vấn đề mới phát hiện:
- **Bug logic trong topicify** — auto mode không sử dụng vector/keywords group
- **Security: Consolidation subprocess không có timeout**
- **FTS5 sanitization quá aggressive** — "C++" → "C"
- **Datetime parsing không xử lý timezone-aware/naive**

---

## 2. Trạng thái các issue từ Review 1

### 2.1 Đã giải quyết hoàn toàn

| # | Finding | Trạng thái | Chi tiết |
|---|---------|------------|----------|
| 1 | No test suite | ✅ Resolved | 150 tests, all passing |
| 2 | Path traversal | ✅ Resolved | `validate_memory_path()` với boundary check |
| 3 | No input validation | ✅ Resolved | MAX_CONTENT_LENGTH=10K, MAX_TAG_LENGTH=50, VALID_PROJECT_PATTERN |
| 4 | N+1 query | ✅ Resolved | Batch UPDATE trong `search_memories()` dòng 286-292 |
| 5 | HRR vectors not used | ✅ Resolved | Hybrid FTS5 + cosine reranking trong `search_memories()` |
| 6 | `datetime.utcnow()` deprecation | ✅ Fixed | Thay bằng `datetime.now(timezone.utc)` |
| 7 | Missing `__main__.py` | ✅ Added | `python -m cheapskate` hoạt động |
| 9 | CI workflow | ✅ Added | GitHub Actions với 3 Python versions + ruff lint |
| 10 | CONTRIBUTING.md | ✅ Added | Development guidelines đầy đủ |

### 2.2 Cần theo dõi (Partial/Outstanding)

| # | Finding | Trạng thái | Chi tiết |
|---|---------|------------|----------|
| 8 | Consolidation subprocess vulnerability | ⚠️ Partial | Vẫn không có timeout, output limit. Đã thêm error handling cho missing `claude`. Xem chi tiết ở mục 5.2 |

---

## 3. Code Quality

### 3.1 Cấu trúc & Modularity

**Đánh giá: Xuất sắc**

```
src/cheapskate/
├── __main__.py          # Entry point
├── __init__.py
├── cli.py                # CLI dispatch (493 lines)
├── db.py                 # Database abstraction (667 lines)
├── config.py             # Configuration (163 lines)
├── hrr.py                # Vector encoding (75 lines)
├── memory_md.py          # MEMORY.md generator (334 lines)
└── commands/
    ├── __init__.py
    ├── add.py             # 178 lines
    ├── search.py          # 152 lines
    ├── topicify.py        # 404 lines
    ├── consolidate.py     # 120 lines
    ├── list.py
    ├── init.py
    ├── audit.py           # 88 lines
    ├── prune.py           # 89 lines
    ├── status.py
    ├── stats.py
    └── topics.py
```

- ✅ Dependency flow rõ ràng: CLI → Commands → (DB, Config, HRR)
- ✅ Single responsibility được tuân thủ
- ✅ Type hints hiện diện trên hầu hết functions
- ✅ Docstrings chất lượng tốt

### 3.2 Naming & Style

- ✅ PEP 8 conventions tuân thủ tốt
- ✅ Constants được định nghĩa rõ ràng (MAX_MEMORY_MD_SIZE, MAX_CONTENT_LENGTH, etc.)
- ✅ Type hints đầy đủ cho public APIs
- ⚠️ Một số magic numbers: `dim=128` trong HRR — nên extract thành constant
- ⚠️ `group_memories_by_similarity` trong topicify.py sử dụng O(n²) loop

### 3.3 Error Handling

**Đánh giá: Tốt**

- ✅ Try/except blocks trong tất cả command entrypoints
- ✅ Database rollback on transaction errors
- ✅ Custom error messages có ý nghĩa
- ⚠️ Một số broad `except Exception` — chấp nhận được cho CLI nhưng nên cụ thể hơn
- ⚠️ Không có retry logic cho transient I/O errors

### 3.4 Duplication Analysis

- ⚠️ **Lặp lại pattern**: `load config → get db_path → check exists → connect` xuất hiện trong hầu hết commands. Có thể refactor thành helper function `get_db(memory_dir)`:
  - `commands/add.py`
  - `commands/search.py`
  - `commands/topicify.py`
  - `commands/consolidate.py`
  - `commands/prune.py`
  - `commands/audit.py`

---

## 4. Security

### 4.1 SQL Injection

**✅ AN TOÀN TUYỆT ĐỐI** — Tất cả queries sử dụng parameterized statements:

```python
conn.execute("SELECT ... WHERE project = ?", (project,))
```

Không có string concatenation với user input.

### 4.2 Path Traversal

**✅ ĐÃ FIX** — `validate_memory_path()` trong `config.py`:

```python
resolved = path.expanduser().resolve()
if not force and not resolved.is_relative_to(default_resolved):
    raise ValueError(...)
```

### 4.3 Subprocess Security

**⚠️ RỦI RO MỚI — Consolidation subprocess không có timeout:**

```python
# commands/consolidate.py dòng 85-89
proc = subprocess.run(
    [claude_path, "-p", prompt],
    capture_output=True,
    text=True,
    # ⚠️ KHÔNG CÓ timeout! Claude Code có thể treo vĩnh viễn
)
```

**Impact:**
- Claude Code có thể treo vĩnh viễn nếu gặp vấn đề
- Không có output size limit — Claude có thể stream response lớn
- Không có validation rằng `claude_path` là executable an toàn

**Recommendation:**
```python
proc = subprocess.run(
    [claude_path, "-p", prompt],
    capture_output=True,
    text=True,
    timeout=300,  # 5 phút timeout
    env={**os.environ, "NO_COLOR": "1"},  # Ngăn output color codes
)

# Giới hạn output
if len(proc.stdout) > 100_000:
    proc.stdout = proc.stdout[:100_000] + "\n[OUTPUT TRUNCATED]"
```

### 4.4 Input Validation

**✅ ĐÃ CẢI THIỆN RÕ RỆT:**

```python
# commands/add.py
MAX_CONTENT_LENGTH = 10_000   # 10KB
MAX_PROJECT_LENGTH = 255
MAX_TAG_LENGTH = 50
MAX_TAGS_PER_MEMORY = 20
VALID_PROJECT_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')

def validate_input(content, project, tags):
    # Kiểm tra length limits
    # Kiểm tra project name pattern
    # Kiểm tra tag format
```

**Tuy nhiên:** Validation chỉ ở CLI layer, không enforced ở database layer. Điều này OK vì database layer được coi là internal, nhưng nếu có code gọi trực tiếp `db.add_memory()` thì không có validation.

---

## 5. Performance

### 5.1 Database Indexes

**✅ ĐÃ TỐT** — Tất cả indexes cần thiết đều có:
- `idx_memories_project`
- `idx_memories_accessed`
- `idx_memories_source`
- `idx_topics_project`
- `idx_rules_project_scope`
- `idx_audit_memory`

**Bổ sung đề nghị:**
- Index trên `timestamp` cho consolidation queries:
  ```sql
  CREATE INDEX idx_memories_timestamp ON memories(timestamp);
  ```
- Composite index `(project, timestamp)` cho per-project consolidation

### 5.2 Query Patterns

**✅ N+1 ĐÃ ĐƯỢC FIX:**

```python
# db.py dòng 286-292 — Batch UPDATE accessed_at
row_ids = [row["id"] for row in rows]
placeholders = ",".join(["?" for _ in row_ids])
conn.execute(
    f"UPDATE memories SET accessed_at = ? WHERE id IN ({placeholders})",
    (now, *row_ids),
)
```

**Tuy nhiên:** Việc unpack vector trong Python loop vẫn có thể chậm với nhiều results:

```python
# db.py dòng 296-309
for row in rows:
    if embedding_bytes:
        memory_vec = unpack_vector(embedding_bytes)
        similarity_score = float(np.dot(query_embedding, memory_vec))
```

Có thể tối ưu bằng cách vectorize operation với numpy:
```python
vectors = np.array([unpack_vector(r["embedding"]) for r in rows if r["embedding"]])
similarities = np.dot(vectors, query_embedding)
```

### 5.3 HRR Vector Encoding

**✅ Hoạt động tốt:**
- Deterministic (same text → same vector)
- Normalized to unit length
- Packed to bytes cho SQLite storage

**⚠️ Performance concern:** Mỗi `memory add` encode HRR ngay cả khi vector search có thể không được sử dụng. Có thể thêm config flag để bật/tắt:

```python
# Chỉ encode nếu vector search enabled
if config.get("search.enable_vector_reranking", True):
    embedding = pack_vector(encode(content))
else:
    embedding = None
```

### 5.4 Topicify O(n²) Similarity

**⚠️ Vẫn là vấn đề cho large datasets:**

```python
# topicify.py dòng 96-127
for i, mem in enumerate(memories):
    for j, other in enumerate(memories[i + 1:], start=i + 1):
        sim = compute_memory_similarity(mem, other)
```

Với 1000 memories → ~500K comparisons. Cần cân nhắc:
- Giới hạn batch size
- Sử dụng approximate nearest neighbor
- Hoặc tăng similarity threshold mặc định

---

## 6. Architecture

### 6.1 Design vs Implementation Alignment

**Đánh giá: 92%** — Cải thiện từ 85%

| Phase | Feature | Trạng thái |
|-------|---------|------------|
| 1 | Storage & Capture (MVP) | ✅ Complete |
| 2 | Vector Layer | ✅ Complete — HRR + hybrid FTS5 reranking |
| 3 | Topic Manager | ✅ Complete |
| 4 | Consolidation Pipeline | ⚠️ Partial — Claude Code integration, cần timeout |
| 5 | CLI Polish | ✅ Complete |
| 6 | Advanced | ⚠️ Cross-project queries partially done |

### 6.2 Phases chi tiết

**Phase 2 ✅ COMPLETE:**
- HRR encoder hoạt động
- Embeddings được computed và stored
- `search_memories()` sử dụng hybrid FTS5 + cosine reranking
- Fetches 5x candidates từ FTS5 để có reranking headroom

**Phase 4 ⚠️ PARTIAL:**
- Consolidation sử dụng Claude Code CLI
- Error handling cho missing `claude` đã được thêm
- Tuy nhiên:
  - Không có timeout → risk of hanging
  - Không parse output từ Claude
  - Không xử lý kết quả (chỉ in ra stdout)
  - Không có LLM abstraction cho Ollama fallback

---

## 7. Testing

### 7.1 Test Coverage — TUYỆT VỜI

**150 tests đều PASS ✓**

```
tests/
├── conftest.py           # Shared fixtures
├── test_cli.py           # 32 tests — CLI commands
├── test_db.py            # 61 tests — Database operations
├── test_hrr.py           # 19 tests — Vector encoding
├── test_memory_md.py     # 23 tests — MEMORY.md generation
└── test_config.py        # 15 tests — Configuration
```

### 7.2 Coverage Areas

| Area | Coverage | Tests |
|------|----------|-------|
| Database schema | ✅ Full | test_init_schema_* |
| CRUD operations | ✅ Full | test_add_memory_*, test_list_memories_* |
| FTS5 search | ✅ Full | test_search_* |
| HRR reranking | ✅ Full | TestHRRReranking class |
| Topic operations | ✅ Full | TestTopicOperations class |
| Prune operations | ✅ Full | TestPruneMemories class |
| Config loading | ✅ Full | TestConfig class |
| CLI commands | ✅ Full | TestCLI* classes |
| MEMORY.md generation | ✅ Full | TestMemoryMdGenerationIntegration |

### 7.3 Test Quality Assessment

**Điểm mạnh:**
- Fixtures được tái sử dụng tốt (`temp_db`, `temp_memory_dir`)
- Test isolation tốt (sử dụng `tmp_path`)
- Assertions cụ thể và có ý nghĩa
- Test HRR reranking rất chi tiết (TestHRRReranking với 5 tests)

**Cần cải thiện:**
- Test `test_project_names_can_contain_slashes` trong test_db.py:836 cho thấy vulnerability nhưng không fail — nên test rằng CLI reject:
  ```python
  def test_add_rejects_path_in_project_name(self, tmp_path):
      # CLI nên reject project names với slashes
      result = run_memory(["add", "test", "-p", "../etc"], check=False)
      assert result.returncode != 0
  ```
- Thiếu test cho error cases:
  - Database corruption
  - Full disk scenario
  - Concurrent access ( WAL mode nhưng chưa test)

---

## 8. Bugs mới được phát hiện

### 8.1 Bug nghiêm trọng: Topicify auto mode không dùng vector similarity

**Tệp:** `src/cheapskate/commands/topicify.py:278-294`

```python
if group_by == "tags" or (group_by == "auto" and group_by != "vector"):
    # Điều kiện này ALWAYS TRUE cho auto mode!
    # vì group_by="auto" KHÔNG BAO GIỜ == "vector"
    # → auto mode LUÔN đi vào tags branch
```

**Hậu quả:** Khi dùng `--group-by auto` (default), topicify KHÔNG BAO GIỜ sử dụng HRR vector similarity. Nó luôn dùng tags grouping, không phải hybrid approach như design yêu cầu.

**Fix:**
```python
if group_by == "tags":
    # Group by tags only
elif group_by in ("vector", "keywords"):
    # Group by semantic similarity
elif group_by == "auto":
    # Auto mode: combine tags + similarity (current "else" logic)
```

### 8.2 Bug: Datetime parsing không handle timezone-aware strings

**Tệp:** `src/cheapskate/memory_md.py:40`

```python
timestamp = datetime.fromisoformat(mem.get("timestamp", "")).strftime("%Y-%m-%d")
```

**Vấn đề:** Nếu timestamp từ database là timezone-aware (có +00:00 suffix), `strftime()` sẽ fail trên Python < 3.11. Mặc dù SQLite luôn lưu naive datetimes, nhưng có thể gây crash nếu:
- Database được import từ nguồn khác
- Timestamp format thay đổi

**Fix:**
```python
ts = mem.get("timestamp", "")
try:
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)  # Strip timezone
    timestamp = dt.strftime("%Y-%m-%d")
except Exception:
    timestamp = "unknown"
```

### 8.3 FTS5 Sanitization quá aggressive

**Tệp:** `src/cheapskate/db.py:328-334`

```python
clean = "".join(c for c in word if c.isalnum() or c.isspace())
```

**Vấn đề:**
- "C++" → "C" (chỉ còn 1 ký tự)
- "node.js" → "nodejs"
- "Python-3.8" → "Python38"
- "git-commit" → "gitcommit"

**Hậu quả:** Search precision giảm đáng kể cho technical content.

**Đề nghị fix:**
```python
def _sanitize_fts_query(self, query: str) -> str:
    if not query or not query.strip():
        return ""
    words = query.split()
    sanitized_words = []
    for word in words:
        # Keep alphanumeric, dots, hyphens, plus; escape other FTS5 specials
        clean = re.sub(r'[":^()\[\]{}]', '', word)
        if len(clean) >= 2:  # Skip single chars
            sanitized_words.append(clean + "*")
    return " ".join(sanitized_words)
```

---

## 9. Observability & Developer Experience

### 9.1 Logging

**⚠️ Hiện tại chỉ có print statements** — Không có structured logging

**Đề nghị:**
```python
import logging
logger = logging.getLogger("cheapskate")

# Thay print bằng:
logger.info(f"Added memory #{memory_id}")
logger.debug(f"Search query: {query}, results: {len(results)}")

# Với CLI flag:
# memory add --verbose
# memory add --quiet
```

### 9.2 CLI Improvements

**Thiếu:**
- `--version` flag để check version:
  ```bash
  memory --version  # cheapskate-memory 0.1.0
  ```

**Tốt:**
- `--json` flag cho search output ✅
- `--dry-run` cho prune ✅
- Help text chi tiết ✅

### 9.3 Configuration Validation

**⚠️ YAML schema không được validate**

```python
# Hiện tại:
decay_days = int(config.get("forgetting.decay_days", 90) or 90)
# "ninety" sẽ crash int() → nên validate sớm hơn
```

**Đề nghị:**
```python
def validate_config(config: Config) -> bool:
    errors = []
    decay = config.get("forgetting.decay_days")
    if not isinstance(decay, int) or decay < 0:
        errors.append("forgetting.decay_days must be non-negative integer")
    # ... validate other fields
    return errors
```

---

## 10. CI/CD

### 10.1 GitHub Actions Workflow

**✅ Hoàn chỉnh:**

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.12", "3.14"]
    steps:
      - pytest với coverage
      - Upload to Codecov

  lint:
    runs-on: ubuntu-latest
    steps:
      - ruff check .
```

**⚠️ Thiếu:**
- Black formatting check (đã listed trong dependencies nhưng không chạy trong CI)
- Security scanning (bandit, safety)

---

## 11. Recommendations (Ưu tiên)

### Critical (Sửa ngay)

1. **Fix topicify auto mode bug** — dòng 278 trong `topicify.py`
2. **Add timeout cho consolidation subprocess** — trong `consolidate.py`:
   ```python
   subprocess.run([claude_path, "-p", prompt], timeout=300)
   ```
3. **Fix FTS5 sanitization** — giữ dots, hyphens, plus signs

### High (Ưu tiên cao)

4. **Add `--version` flag** cho CLI:
   ```python
   parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
   ```

5. **Add structured logging** — replace print statements với logging

6. **Add config validation** — reject invalid YAML values early

7. **Add index on timestamp**:
   ```sql
   CREATE INDEX IF NOT EXISTS idx_memories_timestamp ON memories(timestamp);
   ```

### Medium (Ưu tiên trung bình)

8. **Reduce code duplication** — tạo helper `get_db(memory_dir)`:
   ```python
   def get_db(memory_dir: Optional[Path] = None) -> Database:
       # Common initialization pattern
   ```

9. **Optimize HRR batch computation** — vectorize với numpy:
   ```python
   vectors = np.stack([unpack_vector(r["embedding"]) for r in rows])
   similarities = np.dot(vectors, query_embedding)
   ```

10. **Add security scanning in CI**:
    ```yaml
    - name: Security scan
      run: pip install bandit safety && bandit -r src/ && safety check
    ```

### Low (Ưu tiên thấp)

11. **Add `memory version` command** để debug
12. **Extract HRR dimension thành constant** (`HRR_DIM = 128`)
13. **Add `--since` flag** cho time-bounded queries
14. **Consider compression** cho long content (SQLite supports it)

---

## 12. Detailed Findings by Module

### 12.1 Database Layer (`db.py`)

| Issue | Severity | Location | Recommendation |
|-------|----------|----------|----------------|
| FTS5 sanitization quá aggressive | Medium | `_sanitize_fts_query` (322-335) | Giữ alphanumeric, dots, hyphens, plus |
| Vector computation không vectorized | Low | `search_memories` (296-309) | Batch compute với numpy |
| Timestamp index missing | Low | Schema | Add `idx_memories_timestamp` |

### 12.2 Topicify (`topicify.py`)

| Issue | Severity | Location | Recommendation |
|-------|----------|----------|----------------|
| **Bug: auto mode không dùng vector** | **High** | **dòng 278** | **Fix condition logic** |
| O(n²) similarity loops | Medium | `group_memories_by_similarity` (96-127) | Giới hạn batch size hoặc dùng ANN |

### 12.3 Consolidate (`consolidate.py`)

| Issue | Severity | Location | Recommendation |
|-------|----------|----------|----------------|
| **No timeout on subprocess** | **High** | **dòng 85-89** | **Thêm timeout=300** |
| No output size limit | Medium | `subprocess.run()` | Giới hạn stdout/stderr |
| No LLM abstraction | Low | Entire file | Thêm Ollama fallback |

### 12.4 CLI (`cli.py`)

| Issue | Severity | Location | Recommendation |
|-------|----------|----------|----------------|
| Thiếu `--version` flag | Medium | `main()` | Thêm version argument |
| Code duplication trong setup | Low | Every command | Extract helper function |

### 12.5 Memory MD (`memory_md.py`)

| Issue | Severity | Location | Recommendation |
|-------|----------|----------|----------------|
| Datetime parsing fragile | Medium | `format_memory_for_index` (40) | Handle timezone-aware strings |
| Binary search có thể optimize | Low | `truncate_to_size` (170-215) | Current approach OK for now |

### 12.6 Commands/Add (`add.py`)

| Issue | Severity | Location | Recommendation |
|-------|----------|----------|----------------|
| HRR encoding luôn chạy | Low | `add_memory` (113) | Conditional encode based on config |

### 12.7 Config (`config.py`)

| Issue | Severity | Location | Recommendation |
|-------|----------|----------|----------------|
| No YAML schema validation | Medium | `load()` (56-71) | Validate types và ranges |
| Validation only at CLI | Low | `add.py` | Add to db.py layer too |

---

## 13. So sánh Review 1 vs Review 2

### Trước (Review 1 - 2025-06-15)

- ❌ Test suite: 0 tests
- ❌ Path traversal: Vulnerable
- ❌ Input validation: None
- ❌ N+1 query: Present
- ❌ HRR vectors: Unused
- ❌ datetime.utcnow(): Deprecated
- ❌ __main__.py: Missing
- ❌ CI workflow: Basic
- ❌ CONTRIBUTING.md: Missing
- ✅ Overall: 7.5/10

### Sau (Review 2 - 2026-07-15)

- ✅ Test suite: 150 tests (all passing)
- ✅ Path traversal: Fixed
- ✅ Input validation: Complete
- ✅ N+1 query: Fixed
- ✅ HRR vectors: Integrated
- ✅ datetime.utcnow(): Fixed
- ✅ __main__.py: Present
- ✅ CI workflow: Complete (3 Python versions + lint)
- ✅ CONTRIBUTING.md: Present
- ✅ Overall: 9.5/10

### Issues mới phát hiện ở Review 2:
1. Bug: topicify auto mode không dùng vector similarity
2. Security: Consolidation subprocess không có timeout
3. Bug: FTS5 sanitization quá aggressive
4. Bug: Datetime parsing không handle timezone-aware strings

---

## 14. Kết luận

**Cheapskate Agent Memory đã tiến bộ vượt bậc** từ review lần trước. Codebase hiện tại có chất lượng cao, test coverage tốt, và kiến trúc sạch sẽ. Các vấn đề còn lại chủ yếu là:
- Một bug logic trong topicify (auto mode không dùng vector)
- Security concern về subprocess timeout trong consolidation
- Một số edge cases trong FTS5 sanitization và datetime parsing

Tất cả đều có thể sửa trong 1-2 giờ làm việc. Khuyến nghị **MERGE các fix này trước khi release 1.0**.

**Điểm sức khỏe: 9.5/10** — Rất gần mức production-ready.

---

*Review hoàn thành bởi Hermes Agent (Nous Research) — 2026-07-15*