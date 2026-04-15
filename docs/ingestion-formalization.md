# Ingestion And Formalization

This document explains how a PDF becomes a `FormalizedProblem` in the active system.

## Goal

The ingestion path is supposed to convert a source PDF into a structured problem without bluffing. A weak extraction or ambiguous formalization should stop the run early and leave enough evidence behind to debug the failure.

## Stage 1: PDF Validation

File: `ingestion/validators.py`

`validate_pdf()` checks:
- file exists
- path is a file
- file is not empty
- file size is below the configured cap
- PDF magic bytes are present

Why it exists:
- cheap, deterministic rejection before slower extraction and LLM work

## Stage 2: Extraction

Files:
- `ingestion/extractors/pdf_extractor.py`
- `ingestion/validators.py`

The extraction coordinator tries the highest-quality available extractor first.

Current fallback order:
1. `marker-pdf`
2. `PyMuPDF`

### Marker path

`MarkerPDFExtractor`:
- shells out to `marker_single`
- writes into a managed output directory
- finds the newest markdown artifact produced by the run
- returns raw extracted markdown plus extractor metadata

### PyMuPDF path

`PyMuPDFExtractor`:
- opens the PDF bytes with `fitz`
- extracts page text directly
- returns the concatenated text and page count

### Normalization and diagnostics

After an extractor succeeds, `PDFExtractor.extract_with_report()` calls `inspect_extracted_text()`.

This does two jobs:
- normalize line endings, whitespace, and null bytes
- add quality warnings, including possible scanned or text-light PDFs

The return value is `ExtractionResult`, which contains:
- normalized text
- `ExtractionReport`

The report records:
- extractor used
- fallback attempts
- raw and normalized character counts
- line count
- page count when available
- warnings
- whether the PDF appears scanned or image-heavy

## Stage 3: Chunking

Files:
- `ingestion/chunking/header_chunker.py`
- `ingestion/validators.py`

The current chunker is intentionally simple. It splits by markdown headers and large block boundaries while respecting a max chunk size.

This is not semantic chunking. It is a deterministic preprocessing step for formalization.

### Why deterministic chunking matters

The active run system depends on artifact reuse. A deterministic chunk manifest makes it easier to:
- inspect what the formalizer actually saw
- compare reruns
- reject obviously weak chunk sets

### Chunk reporting

`build_chunk_report()` converts chunk strings into `ChunkReport` and `ChunkRecord` models.

The report captures:
- total chunks
- total characters
- minimum, maximum, and average chunk size
- dropped empty chunks
- warnings
- ordered chunk records with previews

`validate_chunk_report()` rejects pathological chunk outputs, such as chunk sets that are too small to formalize reliably.

## Stage 4: Formalization

Files:
- `ingestion/formalization/formalizer.py`
- `ingestion/formalization/llm_client.py`

The formalizer is a strict, multi-pass conversion step from chunks to `FormalizedProblem`.

### Provider boundary

`llm_client.py` exists so the formalizer does not care whether requests are going through:
- Gemini CLI
- Gemini API with `GOOGLE_API_KEY`

The client also sanitizes prompt and model strings before sending them out.

### Multi-pass flow

`Formalizer.formalize_with_report()` runs three conceptual phases:

1. `extract`
   - ask the model for a best-effort candidate JSON draft
2. `repair`
   - ask the model to rewrite the candidate into valid JSON matching the schema
3. `validate`
   - apply local validation rules before accepting the output

### Why this is fail-closed

The local validator refuses outputs when any of the following is true:
- objective is missing
- no domain tags are present
- `expected_output` is malformed
- confidence is below threshold
- ambiguity notes remain
- `refusal_reason` is set

This means the system prefers an explicit refusal over a plausible but untrustworthy structured problem.

### Formalization report

Every formalization attempt returns a `FormalizationReport`, even when formalization fails.

The report captures:
- accepted or refused
- confidence score
- assumptions
- ambiguity notes
- dropped fields
- validation errors
- refusal reason
- attempt-by-attempt previews and notes
- selected chunk count
- whether an objective was present
- domain tag count
- model used

### Formalized problem

When accepted, `_build_problem()` creates a `FormalizedProblem` with:
- source metadata
- title
- domain tags
- objective
- variables
- constraints
- theoretical framework
- expected output shape
- selected source chunks
- confidence
- formalization metadata

## What Good Handoff Documentation Should Assume

Anyone changing ingestion should understand these invariants:

- extraction must return normalized text plus diagnostics
- chunking must stay inspectable and deterministic unless the contract changes everywhere
- formalization must not silently accept weak or ambiguous outputs
- every early-stage failure should leave enough artifacts behind for `show-run` to explain it
