# Immediate Actions: Critical Fixes

> **Do these first before anything else.** Each item here will cause crashes or garbage output if not fixed.

---

## 🔴 Critical Bug Fixes (Do Today)

### 1. Fix Import Error in Calculus Plugin

**File:** `math_engine/plugins/calculus/plugin.py`

**Problem:** Line 121 uses `Any` without importing it.

**Fix:**
```python
# Add to imports at top of file
from typing import Any, Dict, List, Optional  # Add Any
```

---

### 2. Fix UnboundLocalError in Orchestrator

**File:** `mvp_generator/orchestrator.py`

**Problem:** `design_manifest` may not be defined on retry attempts.

**Current code (lines 56-60):**
```python
# 1. Architecture Design (only on first attempt, or if architect violations)
if attempt == 1 or self._has_architect_violations(report):
    logger.info("Step 1: Architecture design...")
    design_manifest = self.architect.design(math_result)
    logger.info("Designed %d files", len(design_manifest))

# 2. Implementation with feedback
logger.info("Step 2: Algorithm implementation...")
for file_path, purpose in design_manifest.items():  # <-- UnboundLocalError here!
```

**Fix:** Initialize before the loop
```python
def generate_mvp(self, math_result: MathResult, max_retries: int = 5) -> MVPOutput:
    design_manifest = {}  # ADD THIS LINE
    
    for attempt in range(1, max_retries + 1):
        # ... rest of method
```

---

### 3. Fix Missing RAG Data Files

**File:** `ai_tutor/rag/concept_engine.py` expects `data/concepts.jsonl`

**Fix - Option A (Create minimal data):**
```bash
mkdir -p data
echo '{"id": "1", "title": "Calculus", "content": "The study of continuous change"}' > data/concepts.jsonl
```

**Fix - Option B (Make RAG optional):**
```python
# In formalizer.py, make RAG optional
try:
    from ai_tutor.rag.vector_store import VectorStore
    RAG_AVAILABLE = True
except (ImportError, FileNotFoundError):
    RAG_AVAILABLE = False
```

---

### 4. Add LLM Provider Fallback

**File:** `mvp_generator/agents/base_agent.py`

**Problem:** Hardcoded Gemini, no fallback on failure.

**Fix - Add retry decorator:**
```python
# At top of file
from tenacity import retry, stop_after_attempt, wait_exponential

# In BaseSwarmAgent:
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
def _generate(self, prompt: str, ...) -> str:
    """Call the LLM with retry logic."""
    # ... existing code
```

Then install tenacity:
```bash
pip install tenacity
```

---

### 5. Fix HelicOps Mock Mode

**File:** `helicops_critic/integration.py`

**Problem:** Falls back to mock mode too easily, defeating guardrails.

**Fix:** Make mock mode explicit
```python
class HelicOpsIntegration:
    def __init__(self, config_path: Optional[Path] = None, allow_mock: bool = False):
        self.available = HELICOPS_AVAILABLE
        self.allow_mock = allow_mock
        
    def audit_workspace(self, workspace_path: Path) -> GuardrailReport:
        if not self.available:
            if self.allow_mock:
                logger.warning("HelicOps unavailable - using mock")
                return self._mock_report(workspace_path)
            raise RuntimeError(
                "HelicOps not available. Install: "
                "pip install -e ~/Desktop/HelicOps/packages/core "
                "pip install -e ~/Desktop/HelicOps/packages/py"
            )
        # ... rest of method
```

---

## 🟡 Environment Validation (Do This Week)

### 6. Create Startup Validation Script

**Create file:** `research_engine/startup_checks.py`

```python
"""Validate environment before running."""
import shutil
import sys
from pathlib import Path

def validate():
    """Check all required dependencies."""
    errors = []
    
    # Check Python packages
    try:
        import helicops_py
    except ImportError:
        errors.append("helicops-py not installed. Run: pip install -e ~/Desktop/HelicOps/packages/py")
    
    try:
        import marker_pdf
    except ImportError:
        errors.append("marker-pdf not installed. Run: pip install marker-pdf")
    
    # Check CLI tools
    if not shutil.which("marker_single"):
        errors.append("marker_single CLI not found. Run: pip install marker-pdf")
    
    # Check API keys
    import os
    if not os.getenv("GOOGLE_API_KEY"):
        errors.append("GOOGLE_API_KEY not set")
    
    if errors:
        print("❌ Environment validation failed:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    
    print("✅ Environment validation passed")
    return True

if __name__ == "__main__":
    validate()
```

**Call it from cli.py:**
```python
def main():
    # Validate before running commands
    from startup_checks import validate
    validate()
    
    # ... rest of main
```

---

### 7. Create Configuration System

**Create file:** `research_engine/config.yaml`

```yaml
# Default configuration
math_engine:
  plugins:
    - calculus
  timeout_seconds: 300

llm:
  default_provider: gemini
  model: gemini-1.5-pro
  retry_attempts: 3
  
limits:
  max_pdf_size_mb: 100
  max_lines_per_file: 300
  max_retries_mvp: 5

paths:
  workspace_root: /tmp/research_engine

helicops:
  allow_mock: false  # Set to true only for development
```

**Create file:** `research_engine/config_loader.py`

```python
"""Configuration management."""
import os
from pathlib import Path
from typing import Optional
import yaml
from pydantic import BaseModel

class MathEngineConfig(BaseModel):
    plugins: list[str]
    timeout_seconds: int

class LLMConfig(BaseModel):
    default_provider: str
    model: str
    retry_attempts: int

class LimitsConfig(BaseModel):
    max_pdf_size_mb: int
    max_lines_per_file: int
    max_retries_mvp: int

class Config(BaseModel):
    math_engine: MathEngineConfig
    llm: LLMConfig
    limits: LimitsConfig
    paths: dict
    helicops: dict

def load_config(path: Optional[Path] = None) -> Config:
    """Load configuration from file or use defaults."""
    if path is None:
        # Look for config in standard locations
        for location in [
            Path.cwd() / "config.yaml",
            Path.home() / ".research_engine" / "config.yaml",
            Path(__file__).parent / "config.yaml",
        ]:
            if location.exists():
                path = location
                break
    
    if path and path.exists():
        with open(path) as f:
            data = yaml.safe_load(f)
        return Config(**data)
    
    # Return defaults
    return Config(
        math_engine=MathEngineConfig(
            plugins=["calculus"],
            timeout_seconds=300
        ),
        llm=LLMConfig(
            default_provider="gemini",
            model="gemini-1.5-pro",
            retry_attempts=3
        ),
        limits=LimitsConfig(
            max_pdf_size_mb=100,
            max_lines_per_file=300,
            max_retries_mvp=5
        ),
        paths={"workspace_root": "/tmp/research_engine"},
        helicops={"allow_mock": False}
    )
```

---

## 🟢 Quick Wins (High Impact, Low Effort)

### 8. Add Progress Logging

**File:** `ingestion/pipeline.py`

Add logging to show progress:
```python
import logging
logger = logging.getLogger(__name__)

class IngestionPipeline:
    def process(self, pdf_path: Path) -> FormalizedProblem:
        logger.info("[1/3] Extracting text from PDF...")
        md_text = self.extractor.extract(pdf_path)
        
        logger.info("[2/3] Chunking text...")
        chunks = self.chunker.chunk(md_text)
        
        logger.info("[3/3] Formalizing problem...")
        return self.formalizer.formalize(chunks, ...)
```

---

### 9. Add File Size Validation

**File:** `ingestion/extractors/pdf_extractor.py`

```python
def extract(self, pdf_path: Path) -> str:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    # Check file size
    max_size = 100 * 1024 * 1024  # 100MB
    file_size = pdf_path.stat().st_size
    if file_size > max_size:
        raise ValueError(f"PDF too large: {file_size / 1e6:.1f}MB (max 100MB)")
    
    # ... rest of method
```

---

### 10. Add JSON Schema Validation for Agents

**File:** `mvp_generator/agents/architect.py`

```python
def design(self, ...):
    response = self._generate(prompt)
    
    try:
        clean_json = response.strip().strip("```json").strip("```").strip()
        manifest = json.loads(clean_json)
        
        # Validate required fields
        required_files = ["pyproject.toml", "README.md"]
        for f in required_files:
            if f not in manifest:
                logger.warning(f"Agent missing {f}, adding default")
                manifest[f] = f"Auto-generated {f}"
        
        return manifest
    except Exception as e:
        logger.error("Failed to parse agent output: %s", e)
        # Return safe defaults
        return {
            "pyproject.toml": "Project configuration",
            "README.md": "Documentation",
            "src/solver.py": "Core solver",
        }
```

---

## Test These Fixes

After making the fixes above, test with:

```bash
# 1. Check environment
python -c "from startup_checks import validate; validate()"

# 2. Test simple solve
python cli.py solve "\\frac{d}{dx} x^3"

# 3. Test HelicOps integration
python cli.py helicops-status

# 4. Check no import errors
python -c "
from math_engine.plugins.calculus.plugin import CalculusPlugin
from mvp_generator.orchestrator import Orchestrator
from helicops_critic.integration import HelicOpsIntegration
print('✅ All imports successful')
"
```

---

## Order of Operations

1. **Fix the 3 critical bugs** (items 1-3) - 30 minutes
2. **Add environment validation** (item 6) - 30 minutes  
3. **Test the CLI** - 15 minutes
4. **Add retry logic** (item 4) - 1 hour
5. **Add config system** (item 7) - 1 hour

**Total: ~3.5 hours to get from "crashes" to "works most of the time"**
