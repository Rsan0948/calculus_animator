"""Input validation for ingestion pipeline."""

import logging
import re
from pathlib import Path

from engine.state import ChunkRecord, ChunkReport

logger = logging.getLogger(__name__)

MAX_PDF_SIZE_MB = 100
MAX_PDF_SIZE_BYTES = MAX_PDF_SIZE_MB * 1024 * 1024
MIN_EXTRACTED_TEXT_CHARS = 20
MIN_WARNING_TEXT_CHARS = 200
PDF_MAGIC = b"%PDF"
PREVIEW_LENGTH = 80


class ValidationError(Exception):
    """Raised when input validation fails."""


def validate_pdf(pdf_path: Path) -> None:
    """Validate PDF file before processing."""
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if not pdf_path.is_file():
        raise ValidationError(f"Path is not a file: {pdf_path}")

    file_size = pdf_path.stat().st_size
    if file_size > MAX_PDF_SIZE_BYTES:
        raise ValidationError(
            f"PDF too large: {file_size / 1e6:.1f}MB (max {MAX_PDF_SIZE_MB}MB)"
        )
    if file_size == 0:
        raise ValidationError(f"PDF is empty: {pdf_path}")

    try:
        with pdf_path.open("rb") as pdf_file:
            header = pdf_file.read(4)
    except OSError as exc:
        raise ValidationError(f"Cannot read PDF file: {exc}") from exc

    if header != PDF_MAGIC:
        raise ValidationError(
            f"File does not appear to be a valid PDF (bad magic bytes: {header})"
        )

    logger.debug("PDF validation passed: %s (%d bytes)", pdf_path.name, file_size)


def validate_latex(latex: str) -> None:
    """Validate LaTeX expression."""
    if not latex:
        raise ValidationError("LaTeX expression is empty")
    if len(latex) > 10000:
        raise ValidationError(f"LaTeX expression too long: {len(latex)} chars (max 10000)")

    open_braces = latex.count("{")
    close_braces = latex.count("}")
    if open_braces != close_braces:
        raise ValidationError(
            f"Mismatched braces in LaTeX: {open_braces} open, {close_braces} close"
        )

    logger.debug("LaTeX validation passed: %d chars", len(latex))


def normalize_extracted_text(extracted_text: str) -> str:
    """Normalize extractor output and reject obviously unusable results."""
    cleaned = extracted_text.replace("\x00", "")
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = "\n".join(line.rstrip() for line in cleaned.splitlines()).strip()
    if not cleaned:
        raise ValidationError("Extracted text is empty after normalization")

    if len(cleaned) < MIN_EXTRACTED_TEXT_CHARS:
        raise ValidationError(
            "Extracted text is too short to formalize reliably: "
            f"{len(cleaned)} chars (min {MIN_EXTRACTED_TEXT_CHARS})"
        )

    return cleaned


def inspect_extracted_text(extracted_text: str) -> tuple[str, list[str], bool]:
    """Normalize extracted text and produce human-readable diagnostics."""
    cleaned = normalize_extracted_text(extracted_text)
    warnings: list[str] = []

    non_space_count = sum(1 for character in cleaned if not character.isspace())
    alpha_count = sum(1 for character in cleaned if character.isalpha())
    alpha_ratio = alpha_count / max(non_space_count, 1)

    if len(cleaned) < MIN_WARNING_TEXT_CHARS:
        warnings.append(
            "Extracted text is sparse and may not provide enough context for reliable formalization."
        )

    scanned_pdf_suspected = len(cleaned) < MIN_WARNING_TEXT_CHARS or alpha_ratio < 0.35
    if scanned_pdf_suspected:
        warnings.append(
            "The PDF appears text-light or image-heavy; it may be scanned and yield weak extraction results."
        )

    return cleaned, warnings, scanned_pdf_suspected


def validate_chunks(chunks: list[str]) -> None:
    """Validate text chunks."""
    if not chunks:
        raise ValidationError("No text chunks provided")
    if len(chunks) > 1000:
        raise ValidationError(f"Too many chunks: {len(chunks)} (max 1000)")

    non_empty_chunks = [chunk.strip() for chunk in chunks if chunk.strip()]
    if not non_empty_chunks:
        raise ValidationError("All text chunks are empty")

    total_size = sum(len(chunk) for chunk in non_empty_chunks)
    if total_size > 10_000_000:
        raise ValidationError(f"Total chunk size too large: {total_size / 1e6:.1f}MB")

    logger.debug(
        "Chunk validation passed: %d chunks, %d total chars",
        len(non_empty_chunks),
        total_size,
    )


def build_chunk_report(chunks: list[str]) -> ChunkReport:
    """Build a deterministic chunk manifest and summary diagnostics."""
    validate_chunks(chunks)
    normalized_chunks = [chunk.strip() for chunk in chunks if chunk.strip()]
    lengths = [len(chunk) for chunk in normalized_chunks]

    warnings: list[str] = []
    if len(normalized_chunks) == 1 and lengths[0] > 1200:
        warnings.append("Chunking produced a single large chunk; header segmentation may be weak for this document.")
    if len(normalized_chunks) >= 3 and all(length < 40 for length in lengths):
        warnings.append("Chunking produced many tiny chunks, which may weaken formalization context.")
    if sum(lengths) < MIN_WARNING_TEXT_CHARS:
        warnings.append("Total usable chunk text is low for robust formalization.")

    records = [
        ChunkRecord(
            index=index,
            content=chunk,
            character_count=len(chunk),
            preview=_preview_text(chunk),
        )
        for index, chunk in enumerate(normalized_chunks, start=1)
    ]
    average_size = sum(lengths) / len(lengths)

    return ChunkReport(
        total_chunks=len(records),
        total_characters=sum(lengths),
        min_chunk_size=min(lengths),
        max_chunk_size=max(lengths),
        average_chunk_size=average_size,
        dropped_empty_chunks=len(chunks) - len(normalized_chunks),
        warnings=warnings,
        chunks=records,
    )


def validate_chunk_report(report: ChunkReport) -> None:
    """Reject pathological chunk reports before formalization."""
    if report.total_chunks <= 0:
        raise ValidationError("Chunk report contained no usable chunks")
    if report.total_characters < MIN_EXTRACTED_TEXT_CHARS:
        raise ValidationError("Chunk report does not contain enough usable text to formalize")
    if report.total_chunks >= 3 and all(chunk.character_count < 20 for chunk in report.chunks):
        raise ValidationError("Chunk report contains only tiny fragments; formalization would be unreliable")


def _preview_text(text: str) -> str:
    preview = " ".join(text.split())
    if len(preview) <= PREVIEW_LENGTH:
        return preview
    return preview[: PREVIEW_LENGTH - 3] + "..."
