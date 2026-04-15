# Research Engine: Production Readiness Plan

> **Last Updated:** 2026-04-05  
> **Current Status:** Phase 0 POC → Production  
> **Estimated Effort:** 6-8 weeks full-time

---

## Executive Summary

The research_engine is currently a **Phase 0 proof-of-concept** with working architecture but significant gaps in robustness, completeness, and production hardening. This document outlines everything needed to make it production-ready.

---

## Phase 1: Critical Fixes (Week 1) - "It Doesn't Crash"

These must be fixed before any production deployment. The system will crash or produce garbage without these.

### 1.1 Bug Fixes

| Issue | File | Fix |
|-------|------|-----|
| Missing `Any` import | `math_engine/plugins/calculus/plugin.py:121` | Add `from typing import Any` |
| UnboundLocalError | `mvp_generator/orchestrator.py:56` | Initialize `design_manifest = {}` before loop |
| Missing RAG data | `ai_tutor/rag/concept_engine.py` | Create `data/concepts.jsonl` or disable RAG |

### 1.2 External Dependency Validation

Create a startup validation script that checks:

```python
# checks.py - Run at startup
REQUIRED_TOOLS = {
    "marker_single": "marker-pdf>=0.2.0",
    "gemini": "google-generativeai or GOOGLE_API_KEY for API",
}

def validate_environment():
    missing = []
    for tool, install_info in REQUIRED_TOOLS.items():
        if not shutil.which(tool):
            missing.append(f"{tool}: pip install {install_info}")
    if missing:
        raise RuntimeError(f"Missing dependencies:\n" + "\n".join(missing))
```

**Files to create:**
- `research_engine/startup_checks.py`
- Call it from `cli.py` before any command

### 1.3 LLM Provider Abstraction

Currently hardcoded to Gemini. Create a provider router:

```python
# ai_backend/providers/factory.py
class LLMProvider:
    def generate(self, prompt: str, system: str = None) -> str: ...

class GeminiProvider(LLMProvider): ...
class OpenAIProvider(LLMProvider): ...
class DeepSeekProvider(LLMProvider): ...

# Fallback chain: Gemini -> DeepSeek -> (local Ollama)
```

**Files to modify:**
- `ingestion/formalization/formalizer.py` - Use provider factory
- `mvp_generator/agents/base_agent.py` - Use provider factory

---

## Phase 2: Core Functionality (Weeks 2-3) - "It Works End-to-End"

### 2.1 Math Engine Expansion

Currently only calculus works. Add at least:

| Plugin | Library | Priority |
|--------|---------|----------|
| Linear Algebra | NumPy/SymPy matrices | HIGH |
| Statistics | SciPy.stats | MEDIUM |
| Optimization | CVXPY | MEDIUM |

**Files to create:**
```
math_engine/plugins/linear_algebra/
├── __init__.py
├── plugin.py          # Implements MathPlugin
├── parser.py          # Matrix expression parsing
├── solver.py          # Matrix operations
└── step_generator.py  # Step-by-step matrix math
```

### 2.2 Robust PDF Ingestion

Current `pdf_extractor.py` is brittle. Improvements:

1. **Add fallback chain:** marker-pdf → nougat → pdfplumber → PyMuPDF
2. **Add progress indicators** for large PDFs
3. **Add timeout handling** (large papers can take minutes)
4. **Validate output** - check for reasonable text extraction

**Files to modify:**
- `ingestion/extractors/pdf_extractor.py` - Add fallback logic
- `ingestion/extractors/fallback_extractors.py` - New file with backup extractors

### 2.3 Semantic Chunking (Real Implementation)

Current chunker is regex-based. Real implementation:

```python
# ingestion/chunking/semantic_chunker.py
class SemanticChunker:
    def chunk(self, markdown: str) -> List[Chunk]:
        # Parse markdown into sections
        # Preserve LaTeX blocks
        # Chunk by semantic boundaries (sections, theorems)
        # Respect token limits for LLM context
```

**Key features:**
- Preserve LaTeX math blocks (don't split mid-equation)
- Section-aware chunking
- Configurable chunk size (default 4000 tokens)

---

## Phase 3: Robustness (Weeks 4-5) - "It Handles Errors Gracefully"

### 3.1 Retry Logic with Exponential Backoff

All LLM calls need retry logic:

```python
# mvp_generator/agents/base_agent.py
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((RateLimitError, TimeoutError))
)
def _generate(self, prompt: str, ...) -> str:
    ...
```

### 3.2 Structured Error Handling

Replace generic exceptions with structured errors:

```python
# engine/errors.py
class ResearchEngineError(Exception):
    code: str
    message: str
    context: dict

class IngestionError(ResearchEngineError): ...
class MathEngineError(ResearchEngineError): ...
class MVPGenerationError(ResearchEngineError): ...
class ValidationError(ResearchEngineError): ...
```

### 3.3 State Persistence

Currently everything is in-memory. Add persistence:

```python
# engine/persistence.py
class PipelineStateStore:
    def save(self, state: PipelineState) -> str: ...  # Returns run_id
    def load(self, run_id: str) -> PipelineState: ...
    def list_runs(self) -> List[RunSummary]: ...

# SQLite backend for simplicity
# Store: FormalizedProblem, MathResult, MVPOutput
```

**Files to create:**
- `engine/persistence.py`
- `engine/pipeline_state.py` - Wrapper around state + persistence

### 3.4 Input Validation

```python
# ingestion/validators.py
def validate_pdf(pdf_path: Path) -> None:
    """Check file is valid PDF, within size limits."""
    if pdf_path.stat().st_size > 100 * 1024 * 1024:  # 100MB limit
        raise IngestionError("PDF too large", code="pdf_too_large")
    
    # Check magic bytes for PDF
    with open(pdf_path, 'rb') as f:
        header = f.read(4)
        if header != b'%PDF':
            raise IngestionError("Not a valid PDF", code="invalid_pdf")
```

---

## Phase 4: Code Quality Enforcement (Week 6) - "It Produces Good Code"

### 4.1 Actual File Size/Complexity Checks

Currently only prompts mention limits. Add real checks:

```python
# mvp_generator/validators.py
def validate_file_size(content: str, max_lines: int = 300) -> Optional[Violation]:
    lines = content.split('\n')
    if len(lines) > max_lines:
        return Violation(
            check_id="file-size",
            message=f"File has {len(lines)} lines (max {max_lines})",
            severity="medium"
        )
    return None

def validate_complexity(content: str) -> List[Violation]:
    """Check cyclomatic complexity using AST."""
    ...
```

Call these BEFORE writing files to disk in the orchestrator.

### 4.2 Smart Math Validation

Replace string matching with proper math checking:

```python
# helicops_critic/math_validator.py
import sympy

def validate_mathematically(
    generated_result: str, 
    expected_result: str
) -> bool:
    """Use SymPy to check mathematical equivalence."""
    try:
        gen_expr = sympy.sympify(generated_result)
        exp_expr = sympy.sympify(expected_result)
        return sympy.simplify(gen_expr - exp_expr) == 0
    except:
        # Fall back to string matching
        return expected_result in generated_result
```

### 4.3 HelicOps Integration Hardening

Current integration falls back to "mock mode" too easily:

```python
# helicops_critic/integration.py
class HelicOpsIntegration:
    def __init__(self, allow_mock: bool = False):
        self.allow_mock = allow_mock
        
    def audit_workspace(self, workspace_path: Path) -> GuardrailReport:
        if not self.available:
            if self.allow_mock:
                return self._mock_report(workspace_path)
            raise RuntimeError(
                "HelicOps not available. "
                "Install with: pip install -e ~/Desktop/HelicOps/packages/py"
            )
```

In production, `allow_mock=False` so failures are loud.

---

## Phase 5: Operations (Week 7) - "It Runs in Production"

### 5.1 Configuration Management

Replace hardcoded values with config:

```yaml
# config.yaml
math_engine:
  plugins:
    - calculus
    - linear_algebra
  timeout_seconds: 300

llm:
  default_provider: gemini
  fallback_providers: [deepseek, ollama]
  retry_attempts: 3
  
limits:
  max_pdf_size_mb: 100
  max_lines_per_file: 300
  max_retries_mvp: 5

paths:
  workspace_root: /tmp/research_engine
  extraction_dir: /tmp/research_engine/extraction
```

**Files to create:**
- `research_engine/config_loader.py`
- `config.yaml` (default config)
- `config.production.yaml` (production overrides)

### 5.2 Observability

Add structured logging and metrics:

```python
# engine/telemetry.py
import structlog
from prometheus_client import Counter, Histogram

logger = structlog.get_logger()

# Metrics
INGESTION_DURATION = Histogram('ingestion_seconds', 'Time spent ingesting')
MATH_SOLVE_DURATION = Histogram('math_solve_seconds', 'Time solving', ['plugin'])
MVP_GENERATION_DURATION = Histogram('mvp_generation_seconds', 'Time generating MVP')
GUARDRAIL_VIOLATIONS = Counter('guardrail_violations', 'Count by guardrail', ['guardrail_id'])
```

### 5.3 Containerization

Create Dockerfile for deployment:

```dockerfile
# Dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Install marker-pdf
RUN pip install marker-pdf>=0.2.0

# Install HelicOps
COPY --from=helicops /HelicOps/packages/core /tmp/helicops_core
COPY --from=helicops /HelicOps/packages/py /tmp/helicops_py
RUN pip install -e /tmp/helicops_core -e /tmp/helicops_py

# Install research_engine
COPY . /app
RUN pip install -e /app

ENTRYPOINT ["research-engine"]
```

### 5.4 API Server

Convert CLI to service:

```python
# api/main.py
from fastapi import FastAPI, BackgroundTasks
from api.models import IngestRequest, PipelineStatus

app = FastAPI()

@app.post("/pipeline")
async def start_pipeline(
    request: IngestRequest,
    background_tasks: BackgroundTasks
) -> PipelineStatus:
    """Start async pipeline, return job ID."""
    job_id = create_job()
    background_tasks.add_task(run_pipeline, job_id, request)
    return PipelineStatus(job_id=job_id, status="started")

@app.get("/pipeline/{job_id}")
async def get_status(job_id: str) -> PipelineStatus:
    """Get pipeline status and results."""
    return load_status(job_id)
```

---

## Phase 6: Testing & Documentation (Week 8) - "It's Maintainable"

### 6.1 Test Coverage

| Test Type | Coverage Target | Priority |
|-----------|-----------------|----------|
| Unit tests | 80% | HIGH |
| Integration tests | Key paths | HIGH |
| E2E tests | Full pipeline | MEDIUM |
| Property-based tests | Math operations | MEDIUM |

**Files to create:**
```
tests/
├── unit/
│   ├── test_ingestion.py
│   ├── test_formalizer.py
│   ├── test_router.py
│   ├── test_calculus_plugin.py
│   └── test_agents.py
├── integration/
│   ├── test_full_pipeline.py
│   └── test_helicops_integration.py
├── e2e/
│   └── test_paper_to_mvp.py
└── fixtures/
    ├── sample_papers/
    └── expected_outputs/
```

### 6.2 Documentation

| Document | Purpose | Location |
|----------|---------|----------|
| API Reference | Auto-generated from docstrings | `docs/api/` |
| Architecture Decision Records | Why we made key choices | `docs/adr/` |
| Deployment Guide | How to deploy to production | `docs/deployment.md` |
| Troubleshooting | Common issues and fixes | `docs/troubleshooting.md` |
| Contributing Guide | How to add plugins/agents | `CONTRIBUTING.md` |

---

## Quick Start: What To Do Today

If you want to start making this production-ready right now:

### 1. Fix the Critical Bugs (30 minutes)

```bash
# Fix the Any import
echo "from typing import Any" >> math_engine/plugins/calculus/plugin.py

# Fix the UnboundLocalError
sed -i '' '56i\        design_manifest = {}' mvp_generator/orchestrator.py
```

### 2. Validate Your Environment (15 minutes)

```bash
# Create a check script
cat > check_env.py << 'EOF'
import shutil
import sys

checks = [
    ("marker_single", "marker-pdf"),
    ("gemini", "google-generativeai"),
]

all_good = True
for cmd, pkg in checks:
    if not shutil.which(cmd):
        print(f"❌ Missing: {cmd} (pip install {pkg})")
        all_good = False
    else:
        print(f"✅ Found: {cmd}")

sys.exit(0 if all_good else 1)
EOF

python check_env.py
```

### 3. Add Retry Logic (1 hour)

```bash
pip install tenacity
```

Then add `@retry` decorator to `BaseSwarmAgent._generate()`.

### 4. Test End-to-End (30 minutes)

```bash
# Find a simple calculus PDF or use the CLI directly
python cli.py solve "\\frac{d}{dx} x^2"

# If that works, try the full pipeline with a small PDF
python cli.py pipeline path/to/small_paper.pdf
```

---

## Success Criteria

Research Engine is "production ready" when:

- [ ] Can process 10 papers in a row without crashing
- [ ] MVP generation succeeds >80% of the time
- [ ] Math validation passes >90% of the time
- [ ] All HelicOps guardrails pass on generated code
- [ ] Complete pipeline runs in <10 minutes per paper
- [ ] Has >70% test coverage
- [ ] Deployed in a container with health checks
- [ ] Logs are structured and searchable
- [ ] Errors have actionable error messages

---

## Estimated Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| 1: Critical Fixes | 1 week | System doesn't crash |
| 2: Core Functionality | 2 weeks | Works end-to-end |
| 3: Robustness | 2 weeks | Handles errors gracefully |
| 4: Code Quality | 1 week | Produces good code |
| 5: Operations | 1 week | Runs in production |
| 6: Testing & Docs | 1 week | Maintainable |
| **Total** | **8 weeks** | Production ready |

---

*This document is a living spec. Update it as requirements change.*
