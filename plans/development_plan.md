# Research Engine Development Plan

This document outlines the roadmap for transitioning the Research Engine from its current Beta state to a production-ready tool.

## Current State Assessment
*   **Pipeline:** PDF → Markdown → Formalization → Solver → MVP Swarm → HelicOps Critic.
*   **Successes:** Calculus domain is functional; basic natural language support implemented; logic plugin secured; CLI persistence added.
*   **Gaps:** Only Calculus/Logic work reliably; high number of HelicOps violations (type-hints, silent exceptions); no multi-domain orchestration.

---

## Phase 1: Quality & Compliance (Weeks 1-2)
*Goal: Resolve existing technical debt and ensure all code meets HelicOps standards.*

1.  **Type-Hint Remediation:** Add missing type annotations to all core modules (API, Engine, Math Engine) to satisfy `type-hints` guardrail.
2.  **Exception Handling:** Replace `pass` blocks with proper logging and specific exception types across the codebase.
3.  **Path Traversal Fixes:** Audit all `open()`, `os.unlink()`, and `Path()` calls to ensure user input is validated correctly (using the pattern established in `cli.py`).
4.  **Refactor Hotspots:** Break down `api/bridge.py` and `slide_renderer/engine.py` to reduce complexity scores.

## Phase 2: Core Pipeline Hardening (Weeks 3-4)
*Goal: Make the pipeline resilient to transient failures and large inputs.*

1.  **LLM Fallback Strategy:** Implement provider-agnostic LLM calls with fallback from Gemini to Anthropic/OpenAI for critical agent steps.
2.  **Robust PDF Extraction:** Implement timeouts and file size partitioning for the Marker-based PDF extractor to handle 100+ page papers.
3.  **Persistence Layer Completion:** Ensure `Orchestrator` saves every intermediate step of the Agent Swarm to SQLite so work can be resumed.
4.  **Math Validation 2.0:** Replace string-based equivalence checks with SymPy symbolic comparison in the HelicOps Critic.

## Phase 3: Domain Expansion (Weeks 5-8)
*Goal: Support the full planned STEM domain set.*

1.  **Linear Algebra Plugin:** Full implementation of matrix operations, eigenvalues, and decompositions.
2.  **Statistics & Probability:** Implement hypothesis testing and regression analysis plugins.
3.  **Semantic Chunking:** Improve the ingestion layer to use LaTeX-aware chunking instead of header-based regex.
4.  **Optimization Plugin:** Add support for linear and non-linear programming problems.

## Phase 4: Production Readiness (Weeks 9+)
*Goal: Prepare for multi-user deployment and high-volume usage.*

1.  **Async Orchestration:** Move the pipeline to an async/await model to support concurrent processing.
2.  **Web Dashboard:** Develop a frontend for viewing problem history, math steps, and generated code visualizations.
3.  **Benchmark Suite:** Create a dataset of 100+ research papers to track formalization accuracy and code quality.
4.  **Security Audit:** Final HelicOps pass with zero high/critical violations and manual penetration testing.
