# Run Lifecycle

This document explains how the persisted workflow works, how stage state is stored, and how resume and retry-stage are supposed to behave.

## Why Runs Exist

The document workflow used to be a chain of calls. The active architecture treats it as a durable run so the system can answer:

- what stage is executing right now?
- what stage failed?
- what data was produced before failure?
- can the workflow continue without starting over?
- did the input PDF change since the run started?

## Stage Order

The canonical stage sequence lives in `engine/state.py`:

1. `validate_input`
2. `extract`
3. `chunk`
4. `formalize`
5. `route`
6. `solve`
7. `generate_mvp`

The order is used in three places:

- execution
- display
- downstream invalidation during `retry-stage`

## What Each Stage Produces

### `validate_input`

Purpose:
- Confirm the source path is a readable PDF and capture source metadata.

Typical metadata:
- source path
- file size
- source fingerprint

### `extract`

Purpose:
- Produce normalized text and extraction diagnostics.

Typical artifacts:
- `extract/extracted.md`
- `extract/report.json`

### `chunk`

Purpose:
- Produce deterministic text chunks and chunking diagnostics.

Typical artifact:
- `chunks/chunk_report.json`

### `formalize`

Purpose:
- Produce a structured `FormalizedProblem` or a refused formalization report.

Typical artifacts:
- `formalized/problem.json`
- `formalized/formalization_report.json`

### `route`

Purpose:
- Record which plugin should solve the problem and why.

Typical artifact:
- `solve/route.json`

### `solve`

Purpose:
- Persist the final `MathResult` for the selected plugin.

Typical artifact:
- `solve/math_result.json`

### `generate_mvp`

Purpose:
- Produce a generated code workspace, guardrail report, and attempt history.

Typical artifacts:
- `mvp/summary.json`
- MVP workspace directory reference

## Run Records

`RunRecord` is the top-level persisted object. It stores:

- run id
- linked problem id when formalization succeeds
- source path and fingerprint
- command name
- overall status
- current stage
- timestamps
- last error
- config payload

This record answers the operational question: what is this run, and where did it stop?

## Stage Records

`RunStageRecord` stores stage-local state:

- `status`
- `started_at`
- `completed_at`
- `error`
- `metadata`
- `artifacts`

The stage record is what `show-run` reads when it prints the run history.

## Artifact Records

Artifacts are persisted twice:

- on disk under the run directory
- as `RunArtifactRef` entries in SQLite

The SQLite record stores:

- stage name
- artifact type
- path
- summary
- metadata
- content hash when available

The file on disk stores the actual payload.

This split keeps the database light while keeping artifacts inspectable.

## Source Fingerprints And Stale-Source Protection

Each run stores a fingerprint of the original PDF at creation time.

When `resume` or `retry-stage` needs to touch an early stage that still depends on the original source file, `RunService` recomputes the fingerprint and compares it to the stored one.

Expected behavior:
- if the file is unchanged, the run continues
- if the file is missing, the run fails with a structured `source_missing` error
- if the file changed, the run fails with a structured `stale_source` error

This prevents a run from silently mixing old downstream artifacts with a newer source file.

## Resume Semantics

`resume` finds the first stage whose status is one of:

- missing
- `pending`
- `failed`
- `invalidated`

Then it restarts from that point.

Important behavior:
- completed earlier stages are reused
- persisted artifacts are loaded back in where possible
- no downstream stage should run without its required prior artifacts

## Retry-Stage Semantics

`retry-stage <run-id> <stage>` does two things:

1. Mark the selected stage and every downstream stage as `invalidated`
2. Delete persisted artifacts for that stage and downstream stages

Then `RunService` reruns from the requested stage.

This guarantees that downstream artifacts cannot survive after their inputs were intentionally invalidated.

## Failure Semantics

A failed stage should do three things before returning:

1. store a structured error payload
2. persist any useful diagnostic artifacts
3. leave the run resumable

Examples:
- extraction failure should still preserve any available diagnostics
- formalization refusal should preserve `formalization_report.json`
- MVP failure should preserve guardrail and attempt summary data

## How `show-run` Is Supposed To Help

`show-run` is the operator-facing view of a persisted run. It should answer:

- where the run stopped
- what stage succeeded last
- what extractor was used
- whether chunking looked suspicious
- whether formalization was accepted or refused
- which plugin was selected
- whether MVP generation failed on guardrails or math validation

If a failure still requires opening raw files to understand, the run metadata is not detailed enough yet.
