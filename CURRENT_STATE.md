# Research Engine: Current State Assessment

> **Last Updated:** 2026-04-05

---

## System Architecture (What's Built)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         INPUT: Research Paper                           │
│                         Status: ⚠️ Partial                               │
│  - PDF extraction works (marker-pdf)                                    │
│  - No fallback if marker unavailable                                    │
│  - No file size validation                                              │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 1: INGESTION & FORMALIZATION                                     │
│  Status: 🟡 Working but brittle                                          │
│                                                                         │
│  PDFExtractor       ████████░░ 80% - Works, needs fallback chain        │
│  SemanticChunker    ██░░░░░░░░ 20% - Regex only, not semantic           │
│  Formalizer         ██████░░░░ 60% - Hardcoded Gemini, no retry         │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 2: UNIFIED MATH ENGINE                                           │
│  Status: 🟢 Works for calculus only                                      │
│                                                                         │
│  Router             █████████░ 90% - Clean implementation               │
│  CalculusPlugin     █████████░ 90% - Full pipeline working              │
│  LinearAlgebra      ░░░░░░░░░░ 0%  - Not started                        │
│  Statistics         ░░░░░░░░░░ 0%  - Not started                        │
│  Optimization       ░░░░░░░░░░ 0%  - Not started                        │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 3: EXPLAINER                                                     │
│  Status: 🟡 Basic implementation                                         │
│                                                                         │
│  Step Generator     ███████░░░ 70% - Works for calculus                 │
│  Narrative Gen      ░░░░░░░░░░ 0%  - Not started                        │
│  Visual Generator   ███░░░░░░░ 30% - Basic pygame rendering             │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 4+5: MVP GENERATOR + CRITIC                                      │
│  Status: 🟡 Architecture done, needs hardening                           │
│                                                                         │
│  Architect Agent    █████░░░░░ 50% - Prompts work, no validation        │
│  Algorithm Agent    █████░░░░░ 50% - Generates code, no fix loop        │
│  Tester Agent       ████░░░░░░ 40% - Basic tests                        │
│  Integrator Agent   █████░░░░░ 50% - Basic boilerplate                  │
│  Orchestrator       ████░░░░░░ 40% - Has bug on retry                   │
│  HelicOps Critic    ██████░░░░ 60% - Python API integrated              │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Component-by-Component Breakdown

### ✅ Working Well

| Component | Confidence | Notes |
|-----------|------------|-------|
| Pydantic State Models | 95% | Clean, well-typed schemas |
| Math Engine Router | 90% | Clean ABC, good routing logic |
| Calculus Solver Pipeline | 85% | SymPy integration works |
| HelicOps Python API | 80% | Proper imports, 23 guardrails available |
| Agent Architecture | 75% | 4-agent swarm design is sound |

### ⚠️ Working But Needs Improvement

| Component | Confidence | Issues |
|-----------|------------|--------|
| PDF Extraction | 70% | No fallback, no validation |
| Formalizer | 60% | Hardcoded provider, no retry |
| MVP Orchestrator | 50% | Bug on retry, no persistence |
| Math Validation | 40% | String matching, not mathematical |

### ❌ Not Working / Not Started

| Component | Status | Blocker |
|-----------|--------|---------|
| Linear Algebra Plugin | Not started | Need implementation |
| Semantic Chunking | Regex only | Need LaTeX-aware chunker |
| LLM Fallback Chain | Not implemented | Need provider abstraction |
| State Persistence | In-memory only | Need database |
| Retry Logic | Not implemented | Need tenacity integration |
| File Size Checks | Hardcoded only | Need enforcement |

---

## End-to-End Pipeline Test

### What Should Happen

```
PDF Input → Text Extraction → Formalization → Math Solving → MVP Generation → Guardrail Pass
    ↓              ↓               ↓              ↓               ↓              ↓
  Valid?        Parsed?      Structured?    Solved?      Generated?    Violations?
```

### What Actually Happens

```
PDF Input → [Text Extraction] → [Formalization] → [Math Solving] → ⚠️ MVP Generation
                                                                    │
                                                                    └── May crash on retry
                                                                    └── Guardrails may mock
                                                                    └── Math validation weak
```

**Current Success Rate Estimate:**
- Simple calculus PDF → MVP: ~60%
- Complex paper: ~30%
- Non-calculus paper: ~5% (fails at math engine)

---

## Critical Path to Production

### Path 1: Make It Not Crash (Priority 1)

1. Fix `Any` import in calculus plugin
2. Fix `UnboundLocalError` in orchestrator
3. Add environment validation
4. Add retry logic for LLM calls

**Impact:** Gets success rate from 60% → 85%

### Path 2: Make It Produce Quality Code (Priority 2)

1. Fix HelicOps mock mode (enforce real guardrails)
2. Add file size/complexity enforcement
3. Improve math validation (use SymPy equivalence)
4. Add better agent feedback loops

**Impact:** Gets code quality from "compiles" → "production-ready"

### Path 3: Make It Handle More Math (Priority 3)

1. Implement Linear Algebra plugin
2. Implement Statistics plugin
3. Improve semantic chunking

**Impact:** Expands domain coverage from calculus-only → general STEM

---

## Resource Requirements

### To Get to "Works Reliably" (Path 1)

- **Time:** 1 week
- **Dependencies:** tenacity, pyyaml
- **Skills:** Python debugging, error handling

### To Get to "Production Ready" (All Paths)

- **Time:** 6-8 weeks
- **Dependencies:** See PRODUCTION_READINESS.md
- **Skills:** Python, math libraries, LLM APIs, testing, DevOps

---

## Quick Wins

These would have high impact with low effort:

1. **Add the 3 critical bug fixes** → Stops crashes
2. **Add progress logging** → Better UX
3. **Add file size validation** → Prevents hangs
4. **Add JSON schema validation for agents** → Better error messages
5. **Create a simple test script** → Know if it's working

---

## Red Flags (Must Fix Before Production)

🚩 **Mock mode fallback** - Guardrails don't actually run if HelicOps unavailable
🚩 **No input validation** - Can crash on bad PDFs
🚩 **No retry logic** - Transient failures kill the whole pipeline
🚩 **String-based math validation** - False negatives on equivalent forms
🚩 **No persistence** - Lose all work if process dies
🚩 **Single math domain** - Only calculus works

---

## Green Lights (What's Working)

✅ **Clean architecture** - Well-separated layers
✅ **Pydantic models** - Type-safe state management
✅ **HelicOps integration** - 23 guardrails available via Python API
✅ **Agent swarm design** - Good foundation for code generation
✅ **Calculus pipeline** - End-to-end works for this domain

---

## Recommendation

**Short term (this week):** Fix the 3 critical bugs and add environment validation. This gets you from "demo-ware" to "usable tool."

**Medium term (next month):** Implement Path 2 (quality enforcement). This gets you from "usable" to "trustworthy."

**Long term (2 months):** Implement Path 3 (more math domains). This gets you from "calculus solver" to "research engine."
