# User Guide

This guide covers the active `research-engine` CLI path.

## Install

Basic editable install:

```bash
pip install -e ".[dev]"
```

Full install for document workflows:

```bash
pip install -e ".[dev,llm,pdf,guardrails]"
```

Formalization requirements:
- Gemini CLI on your path, or
- `GOOGLE_API_KEY` set in the environment

## Fastest Ways To Use The App

### Solve a math problem directly

```bash
research-engine solve "derivative of x^3"
research-engine solve "mean of [1,2,3,4,5]"
research-engine solve "eigenvalues of [[1,2],[3,4]]"
```

This path:
- detects the domain
- builds a `FormalizedProblem`
- routes to the best plugin
- persists the latest result in SQLite

### Run a persisted document workflow

```bash
research-engine run paper.pdf
```

This path:
- creates a persisted run
- validates the PDF
- extracts text
- chunks the text
- formalizes a structured problem
- routes and solves it
- generates and audits an MVP

## Core Commands

### `research-engine run <pdf>`

Use this for the main product path.

### `research-engine runs`

List persisted runs in reverse chronological order.

### `research-engine show-run <run-id>`

Inspect one run in detail, including stage history and early-stage diagnostics.

### `research-engine resume <run-id>`

Resume the first failed or incomplete stage.

### `research-engine retry-stage <run-id> <stage>`

Invalidate a stage and everything after it, then rerun from that point.

Useful stages:
- `formalize`
- `route`
- `solve`
- `generate_mvp`

### `research-engine pipeline <pdf>`

Compatibility wrapper around `run`.

### `research-engine ingest <pdf>`

Direct ingestion command. Useful when you want the structured problem without the full persisted run workflow.

### `research-engine solve <expression>`

Direct solver command for CLI-style math inputs.

### `research-engine domains`

Show domain support maturity and recommended input types.

### `research-engine surfaces`

Show which repo surfaces are active, transitional, and legacy.

### `research-engine list`

List persisted problems.

### `research-engine show <problem-id>`

Show one persisted problem and its latest outputs.

## Reading A Run

`show-run` is the most useful operator command.

Things to look for:
- did `validate_input` capture the correct file size and fingerprint?
- which extractor ran?
- were there extraction warnings?
- how many chunks were produced?
- was formalization accepted or refused?
- which plugin was selected in `route`?
- did `generate_mvp` fail on guardrails or math validation?

## Common Failure Modes

### Formalization refusal

Meaning:
- the system extracted text, but could not produce a high-confidence structured problem

What to inspect:
- `extract/report.json`
- `chunks/chunk_report.json`
- `formalized/formalization_report.json`

### Unsupported routing

Meaning:
- no plugin had enough confidence for the problem’s domain tags and objective

What to inspect:
- `solve/route.json`
- `research-engine domains`

### Stale-source failure on resume

Meaning:
- the original PDF changed after the run was created, or it is now missing

What to do:
- start a fresh run for the new file
- only use `resume` when the original source artifact is still the same file

### MVP validation failure

Meaning:
- the generated code did not pass HelicOps or math validation

What to inspect:
- `mvp/summary.json`
- attempt history in `show-run`

## Database And Run Storage

SQLite database:
- `~/.research_engine/state.db`

Run artifact root:
- `~/.research_engine/runs/`

## Recommended Docs After This Guide

- `docs/architecture.md`
- `docs/code-map.md`
- `docs/run-lifecycle.md`
- `docs/ingestion-formalization.md`
- `docs/math-engine.md`
- `docs/mvp-generation.md`
