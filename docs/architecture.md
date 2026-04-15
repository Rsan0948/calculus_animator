# Architecture Guide

This document explains the active `research-engine` product path. It is written for handoff and maintenance, not for the legacy tutor or animator surfaces that still exist elsewhere in the repo.

## Active Boundary

The current product boundary is:

- `cli.py`
- `startup_checks.py`
- `engine/`
- `ingestion/`
- `math_engine/`
- `mvp_generator/`
- `helicops_critic/`
- `tests/` for unit and integration coverage of the path above

Everything else in the repository should be treated as legacy or transitional unless a newer document explicitly says otherwise.

## System Shape

The active workflow is a persisted run graph:

```text
CLI command
  -> RunService
    -> validate_input
    -> extract
    -> chunk
    -> formalize
    -> route
    -> solve
    -> generate_mvp
  -> StateManager persists run, stage, artifact, problem, result, and MVP state
```

There are two user-facing entry patterns:

- `research-engine solve <expression>` for direct math solving
- `research-engine run <paper.pdf>` for the persisted document workflow

`pipeline` is now a compatibility wrapper around `run`.

## Core Design Rules

### 1. State is explicit

The engine uses Pydantic models in `engine/state.py` as the shared contract between ingestion, routing, solving, MVP generation, and persistence. New features should extend those models before they invent new ad hoc payloads.

### 2. Runs are first-class

A document workflow is not an in-memory chain of calls. It is a `RunRecord` with ordered `RunStageRecord` entries and persisted `RunArtifactRef` outputs. This is what enables inspection, resume, retry-stage, and post-failure debugging.

### 3. Fail closed in early stages

Extraction, chunking, and formalization all reject weak inputs instead of silently inventing structure. If a paper cannot be formalized with enough confidence, the run should stop at `formalize` with inspectable artifacts.

### 4. Routing is inspectable

The math engine separates routing analysis from solver execution. `Router.analyze()` records which plugin scored highest and why, while `Router.solve_with_analysis()` executes against that recorded decision.

### 5. Generated code is audited

The MVP generator does not stop at code generation. It performs local validation, runs the HelicOps critic, and records attempt history so failures are visible instead of disappearing behind a final boolean.

## Subsystem Responsibilities

### CLI layer

`cli.py` is the operational entry point. It validates arguments, calls the run service or direct solve path, and renders human-readable summaries. It should stay thin: business logic belongs in `engine/`, `ingestion/`, `math_engine/`, and `mvp_generator/`.

### Engine layer

`engine/state.py` defines the canonical models.

`engine/state_manager.py` is the SQLite boundary. It stores:

- problems
- math results
- MVP outputs
- runs
- run stages
- run artifacts

`engine/run_service.py` is the workflow coordinator. It owns stage ordering, artifact writing, stale-source protection, resume, and retry-stage semantics.

`engine/repo_inventory.py` documents which repo surfaces are active, transitional, or legacy.

### Ingestion layer

`ingestion/extractors/pdf_extractor.py` turns PDFs into normalized text plus an extraction report.

`ingestion/chunking/header_chunker.py` converts extracted text into deterministic chunks.

`ingestion/validators.py` hardens PDF input, normalized text, and chunk quality.

`ingestion/formalization/formalizer.py` converts chunks into a strict `FormalizedProblem` plus a `FormalizationReport`.

`ingestion/formalization/llm_client.py` isolates formalizer model access.

### Math engine

`math_engine/input_parser.py` converts natural language into structured JSON for plugins that need it.

`math_engine/router.py` scores plugins, records routing metadata, and executes the selected solver.

`math_engine/plugin_registry.py` is the plugin registration and domain-maturity map.

`math_engine/base_plugin.py` defines the plugin contract all domain solvers must satisfy.

### MVP and audit layer

`mvp_generator/orchestrator.py` runs the multi-agent code generation loop.

`mvp_generator/validators.py` performs local pre-write validation.

`helicops_critic/integration.py`, `runner.py`, and `math_validator.py` convert HelicOps and oracle-based math checks into a `GuardrailReport`.

## Persistence Model

There are two overlapping persistence layers:

- Problem-centric persistence: `problems`, `math_results`, `mvp_outputs`
- Run-centric persistence: `runs`, `run_stages`, `run_artifacts`

The problem-centric tables are useful for looking up the latest solved state of a problem.

The run-centric tables are the execution source of truth for the current workflow. They answer questions like:

- what stage failed?
- what artifact was produced?
- what changed between attempts?
- can the run be resumed?

## Artifact Layout

By default, run artifacts live under `~/.research_engine/runs/<run_id>/`.

Important artifact groups:

- `extract/extracted.md`
- `extract/report.json`
- `chunks/chunk_report.json`
- `formalized/problem.json`
- `formalized/formalization_report.json`
- `solve/route.json`
- `solve/math_result.json`
- `mvp/summary.json`
- generated MVP workspace directory

## Recommended Reading Order For Handoff

1. `README.md`
2. `docs/code-map.md`
3. `docs/run-lifecycle.md`
4. `docs/ingestion-formalization.md`
5. `docs/math-engine.md`
6. `docs/mvp-generation.md`
7. `tests/integration/test_cli.py`
8. `tests/unit/test_run_service.py`

## What To Extend First

When expanding the active platform, start here:

- add or strengthen run-stage metadata before changing CLI output
- extend `engine/state.py` models before introducing new JSON shapes
- update `StateManager` and `RunService` together for workflow changes
- add or refine plugin parser support before loosening solver inputs
- add tests around CLI and run persistence before touching legacy surfaces
