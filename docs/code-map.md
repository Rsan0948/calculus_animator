# Code Map

This file is the handoff inventory for the active `research-engine` code path. It explains what each active module is for, what it consumes, and what it emits.

## Entry Points

### `cli.py`

Purpose:
- User-facing command-line interface for the active product path.

What it does:
- Defines help text and argparse wiring for all supported commands.
- Runs direct solve flows for `solve`.
- Runs persisted document workflows for `run`, `pipeline`, `resume`, and `retry-stage`.
- Reads run artifacts back out for `show-run`.
- Exposes non-execution inspection commands such as `domains`, `surfaces`, `runs`, `list`, and `show`.

Important functions:
- `run_document()` and `run_pipeline()`: wrapper functions for persisted document workflows.
- `resume_run()` and `retry_stage()`: recovery operations for failed or incomplete runs.
- `solve()`: direct CLI solve path through `Router` and `StateManager`.
- `show_run()`: renders stage summaries and artifact-backed diagnostics.
- `show_domains()` and `show_surfaces()`: operational inspection commands for support maturity and repo boundaries.
- `main()`: argument parsing and command dispatch.

### `startup_checks.py`

Purpose:
- Environment validation for local setup and quickstart flows.

What it does:
- Verifies package dependencies, CLI tool presence, environment variables, and required directories.
- Encodes command-specific expectations in `CommandValidator`.
- Knows that ingestion requires either Gemini CLI or `GOOGLE_API_KEY`, and that PDF workflows need an available extractor.

## Engine Layer

### `engine/state.py`

Purpose:
- Shared schema contract for the whole active system.

Key model groups:
- Source and problem definition: `SourceDocument`, `Variable`, `Constraint`, `ExpectedOutput`, `FormalizedProblem`
- Ingestion diagnostics: `ExtractionReport`, `ExtractionResult`, `ChunkRecord`, `ChunkReport`, `FormalizationAttemptReport`, `FormalizationReport`
- Solver output: `VisualHint`, `MathStep`, `MathResult`
- MVP audit output: `Violation`, `GuardrailReport`, `GeneratedFile`, `MVPAttempt`, `MVPOutput`
- Run orchestration state: `RunArtifactRef`, `RunStageRecord`, `RunRecord`

Operational constants:
- `RUN_STAGE_SEQUENCE` defines the ordered persisted workflow.
- `RUN_STAGE_ORDER` supports sorting and downstream invalidation.

### `engine/state_manager.py`

Purpose:
- SQLite persistence boundary.

What it owns:
- Schema initialization for all active tables.
- Save and lookup methods for `FormalizedProblem`, `MathResult`, and `MVPOutput`.
- Full run lifecycle persistence through `create_run`, `start_stage`, `complete_stage`, `fail_stage`, `complete_run`, `get_run`, `get_run_stages`, `get_run_artifacts`, and `invalidate_stage_and_downstream`.

How it is supposed to work:
- Runs are updated stage-by-stage.
- Stage metadata and artifacts are written together so failures remain inspectable.
- `invalidate_stage_and_downstream()` is the backbone for `retry-stage`.
- Problem-centric persistence remains available for quick retrieval of the latest outputs.

### `engine/run_service.py`

Purpose:
- First-class workflow orchestrator for persisted document runs.

What it does:
- Creates new runs with source fingerprints.
- Executes the ordered stage graph.
- Loads prior artifacts when resuming downstream stages.
- Rejects stale or missing source PDFs when an early-stage rerun still depends on the original file.
- Persists all stage artifacts into the run directory and registers them in SQLite.

Important public methods:
- `run_pdf()`: create and execute a new run.
- `resume_run()`: continue from the first failed, pending, or invalidated stage.
- `retry_stage()`: invalidate one stage and everything after it, then rerun.
- `get_run()` and `list_runs()`: inspection helpers used by the CLI.

Important private responsibilities:
- `_execute_run()`: stage graph executor.
- `_ensure_source_is_current()`: stale-source safety check.
- `_write_text_artifact()` and `_write_json_artifact()`: managed artifact persistence.
- `_load_problem()`, `_load_math_result()`, `_load_chunks()`: reuse persisted outputs on resume.

### `engine/repo_inventory.py`

Purpose:
- Machine-readable declaration of active, transitional, and legacy repo surfaces.

What it is for:
- Preventing architectural drift.
- Making `research-engine surfaces` honest.
- Showing future contributors what is safe to treat as the current product boundary.

## Ingestion Layer

### `ingestion/pipeline.py`

Purpose:
- Older direct ingestion wrapper that still exists as a simpler path around extraction, chunking, and formalization.

Role today:
- Still part of the repo, but the persisted `RunService` workflow is the more important operational path.
- Useful to read for subsystem composition, but not the source of truth for run persistence.

### `ingestion/validators.py`

Purpose:
- Deterministic validation and normalization for early pipeline stages.

What it does:
- `validate_pdf()`: rejects missing files, empty files, oversized PDFs, and bad magic bytes.
- `normalize_extracted_text()` and `inspect_extracted_text()`: clean extractor output and add quality warnings.
- `validate_chunks()`, `build_chunk_report()`, `validate_chunk_report()`: convert chunking into a deterministic report and reject pathological chunk sets.

### `ingestion/extractors/pdf_extractor.py`

Purpose:
- Multi-extractor PDF text extraction with diagnostics.

Classes:
- `BasePDFExtractor`: abstract extractor interface.
- `MarkerPDFExtractor`: preferred path using `marker_single`.
- `PyMuPDFExtractor`: fallback extractor when marker is unavailable or fails.
- `PDFExtractor`: fallback coordinator that normalizes output and builds `ExtractionReport`.

How it is supposed to work:
- Try the highest-quality available extractor first.
- Normalize and inspect the extracted text before returning it.
- Record fallback attempts and warnings rather than hiding them.

### `ingestion/chunking/header_chunker.py`

Purpose:
- Deterministic chunking by markdown headers and block boundaries.

What it is supposed to do:
- Split extracted text into reasonably sized chunks for formalization.
- Stay simple and predictable.
- Leave semantic chunking for a future, separate implementation.

### `ingestion/formalization/llm_client.py`

Purpose:
- Provider boundary for formalization LLM calls.

What it does:
- Detects Gemini CLI availability.
- Detects API availability through `GOOGLE_API_KEY`.
- Sanitizes prompt and model inputs before making external calls.
- Gives the formalizer one stable function to call instead of scattering provider logic.

### `ingestion/formalization/formalizer.py`

Purpose:
- Strict multi-pass conversion from chunks to `FormalizedProblem`.

What it does:
- Validates chunks before any model call.
- Runs candidate extraction and repair passes.
- Extracts JSON from the model response.
- Applies local validation rules, including minimum confidence and ambiguity refusal.
- Returns either an accepted `FormalizedProblem` or a refused result with a `FormalizationReport`.

Important design choice:
- This stage fails closed. If the model is uncertain or ambiguous, the run should stop instead of inventing a plausible-looking problem statement.

## Math Engine

### `math_engine/base_plugin.py`

Purpose:
- Abstract contract for domain plugins.

What plugins must provide:
- `name`
- `supported_domains`
- `can_solve(problem)`
- `solve(problem)`

### `math_engine/input_parser.py`

Purpose:
- Translate natural language into structured JSON for plugins that benefit from it.

Supported domains:
- linear algebra
- statistics
- graph theory
- logic
- number theory
- combinatorics
- optimization

Important behavior:
- The parser is intentionally shallow and rule-based.
- It is not a full symbolic understanding layer.
- It should only normalize obvious inputs into shapes plugins already understand.

### `math_engine/router.py`

Purpose:
- Routing and execution boundary for domain solvers.

What it does:
- Scores registered plugins with `can_solve()`.
- Returns an inspection payload from `analyze()`.
- Pre-parses natural-language objectives into JSON for non-calculus plugins when needed.
- Executes the selected plugin via `solve_with_analysis()`.
- Persists direct solve results when a `StateManager` is attached.

### `math_engine/plugin_registry.py`

Purpose:
- Central registration and support metadata map for plugins.

What it does:
- Registers all available plugins.
- Publishes domain support status and recommended input shape.
- Powers `research-engine domains`.

### Domain plugins

Active plugin modules:
- `math_engine/plugins/calculus/plugin.py`
- `math_engine/plugins/linear_algebra/plugin.py`
- `math_engine/plugins/statistics/plugin.py`
- `math_engine/plugins/optimization/plugin.py`
- `math_engine/plugins/number_theory/plugin.py`
- `math_engine/plugins/combinatorics/plugin.py`
- `math_engine/plugins/graph_theory/plugin.py`
- `math_engine/plugins/logic/plugin.py`

What they are supposed to do:
- Accept a `FormalizedProblem` whose `objective` may already be structured JSON.
- Return a `MathResult` with explicit success or failure.
- Avoid fabricating defaults when required inputs are missing.
- Keep domain-specific solving logic out of the router.

## MVP Generation And Audit

### `mvp_generator/orchestrator.py`

Purpose:
- Coordinates the multi-agent MVP generation loop.

What it does:
- Uses architect, algorithm, tester, and integrator agents to assemble a small implementation package.
- Runs local validators before writing files.
- Runs the HelicOps critic after writing files.
- Feeds violations back into the next attempt.
- Records per-attempt history in `MVPAttempt`.

### `mvp_generator/validators.py`

Purpose:
- Cheap local validation before the critic stage.

Checks:
- file size
- Python syntax
- presence of required files

Why it exists:
- It catches obvious failures before the heavier HelicOps audit.

### `helicops_critic/integration.py`

Purpose:
- Direct Python integration with installed HelicOps packages.

What it does:
- Loads guardrail configuration.
- Discovers Python files in the generated workspace.
- Runs file-based guardrails.
- Converts raw guardrail output into `Violation` and `GuardrailReport` models.

### `helicops_critic/runner.py`

Purpose:
- High-level critic used by the orchestrator.

What it does:
- Runs HelicOps workspace audit.
- Runs math validation against the original solver output when available.
- Assigns violation classes back to the relevant swarm agent.

### `helicops_critic/math_validator.py`

Purpose:
- Oracle check for generated MVP correctness.

What it does:
- Executes generated `main.py` or `src/main.py`.
- Extracts an answer from program output.
- Compares it to the stored `MathResult.final_answer` using string checks and SymPy equivalence where possible.

## Test Files Worth Reading First

- `tests/integration/test_cli.py`: end-to-end CLI expectations for the active path.
- `tests/unit/test_run_service.py`: run graph, artifact, and resume behavior.
- `tests/unit/test_state_manager.py`: persistence behavior and round-tripping.
- `tests/unit/test_formalizer.py`: formalization acceptance and refusal behavior.
