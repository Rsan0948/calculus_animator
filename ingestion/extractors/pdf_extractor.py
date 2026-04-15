"""PDF to Markdown extractor with fallback support."""

import logging
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from engine.state import ExtractionReport, ExtractionResult
from ingestion.validators import ValidationError, inspect_extracted_text

logger = logging.getLogger(__name__)


class PDFExtractionError(Exception):
    """Raised when PDF extraction fails."""


class BasePDFExtractor(ABC):
    """Abstract base class for PDF extractors."""

    @abstractmethod
    def extract_with_report(self, pdf_path: Path) -> ExtractionResult:
        """Extract text from PDF and return both text and extractor diagnostics."""

    def extract(self, pdf_path: Path) -> str:
        """Compatibility helper returning only extracted text."""
        return self.extract_with_report(pdf_path).text

    def is_available(self) -> bool:
        """Check if this extractor is available."""
        return True


class MarkerPDFExtractor(BasePDFExtractor):
    """Extracts text using marker-pdf (best quality)."""

    def __init__(self, output_dir: Optional[Path] = None) -> None:
        self.output_dir = output_dir or Path("/tmp/research_engine/extraction")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def is_available(self) -> bool:
        return shutil.which("marker_single") is not None

    def extract_with_report(self, pdf_path: Path) -> ExtractionResult:
        """Run marker on the PDF and return the extracted markdown text."""
        if not self.is_available():
            raise PDFExtractionError("marker_single not found. Install with: pip install marker-pdf")

        existing_files = {
            path.resolve()
            for path in self.output_dir.rglob("*.md")
            if path.is_file()
        }
        cmd = [
            "marker_single",
            str(pdf_path),
            "--output_dir",
            str(self.output_dir),
            "--batch_multiplier",
            "2",
        ]

        try:
            logger.info("Extracting PDF with marker-pdf: %s", pdf_path.name)
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=300,
            )

            md_path = self._find_new_markdown_file(existing_files)
            return ExtractionResult(
                text=md_path.read_text(encoding="utf-8"),
                report=ExtractionReport(
                    extractor_used="marker-pdf",
                    extractor_metadata={"artifact_path": str(md_path)},
                ),
            )
        except subprocess.TimeoutExpired as exc:
            raise PDFExtractionError("Marker timed out after 5 minutes") from exc
        except subprocess.CalledProcessError as exc:
            raise PDFExtractionError(f"Marker failed: {exc.stderr}") from exc

    def _find_new_markdown_file(self, existing_files: set[Path]) -> Path:
        """Locate the newest markdown artifact produced by marker."""
        candidates = [
            path for path in self.output_dir.rglob("*.md")
            if path.is_file() and path.resolve() not in existing_files
        ]
        if not candidates:
            candidates = [path for path in self.output_dir.rglob("*.md") if path.is_file()]
        if not candidates:
            raise PDFExtractionError("Marker did not produce any markdown artifacts")
        return max(candidates, key=lambda path: path.stat().st_mtime)


class PyMuPDFExtractor(BasePDFExtractor):
    """Last resort extractor using PyMuPDF (fitz)."""

    def __init__(self) -> None:
        self._available = None

    def is_available(self) -> bool:
        if self._available is None:
            try:
                import fitz  # noqa: F401

                self._available = True
            except ImportError:
                self._available = False
        return self._available

    def extract_with_report(self, pdf_path: Path) -> ExtractionResult:
        """Extract text using PyMuPDF."""
        if not self.is_available():
            raise PDFExtractionError("PyMuPDF not installed. Install with: pip install pymupdf")

        try:
            import fitz

            logger.info("Extracting PDF with PyMuPDF: %s", pdf_path.name)

            with pdf_path.open("rb") as pdf_file:
                pdf_bytes = pdf_file.read()

            text_parts = []
            with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                page_count = len(doc)
                for page in doc:
                    text_parts.append(page.get_text())

            return ExtractionResult(
                text="\n\n".join(text_parts),
                report=ExtractionReport(
                    extractor_used="pymupdf",
                    page_count=page_count,
                ),
            )
        except Exception as exc:
            raise PDFExtractionError(f"PyMuPDF failed: {exc}") from exc


class PDFExtractor:
    """Main PDF extractor with automatic fallback chain.

    Tries extractors in order:
    1. marker-pdf (best quality)
    2. PyMuPDF (fallback while additional extractors are hardened)
    """

    def __init__(self, output_dir: Optional[Path] = None) -> None:
        self.extractors = [
            MarkerPDFExtractor(output_dir),
            PyMuPDFExtractor(),
        ]

    def extract_with_report(self, pdf_path: Path) -> ExtractionResult:
        """Extract text from PDF using the best available extractor."""
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        errors: list[str] = []
        for extractor in self.extractors:
            if not extractor.is_available():
                continue

            try:
                result = extractor.extract_with_report(pdf_path)
                normalized_text, warnings, scanned_pdf_suspected = inspect_extracted_text(result.text)
                report = result.report.model_copy(deep=True)
                report.fallback_attempts = errors.copy()
                report.raw_character_count = len((result.text or "").strip())
                report.normalized_character_count = len(normalized_text)
                report.line_count = len([line for line in normalized_text.splitlines() if line.strip()])
                report.scanned_pdf_suspected = scanned_pdf_suspected
                report.warnings.extend(warnings)
                return ExtractionResult(text=normalized_text, report=report)
            except (PDFExtractionError, ValidationError) as exc:
                logger.warning("Extractor %s failed: %s", type(extractor).__name__, exc)
                errors.append(f"{type(extractor).__name__}: {exc}")

        raise PDFExtractionError(
            "All PDF extractors failed:\n" + "\n".join(errors)
        )

    def extract(self, pdf_path: Path) -> str:
        """Compatibility helper returning only extracted text."""
        return self.extract_with_report(pdf_path).text
