"""Ingestion pipeline: PDF -> Markdown -> Semantic Chunks -> FormalizedProblem."""

import logging
from pathlib import Path
from typing import Optional

from engine.state import FormalizedProblem, SourceDocument
from engine.state_manager import StateManager
from ingestion.chunking.header_chunker import HeaderChunker
from ingestion.extractors.pdf_extractor import PDFExtractor, PDFExtractionError
from ingestion.formalization.formalizer import Formalizer, FormalizationError
from ingestion.validators import validate_pdf, ValidationError

logger = logging.getLogger(__name__)


class IngestionError(Exception):
    """Raised when ingestion fails."""
    pass


class IngestionPipeline:
    """Orchestrates the conversion from raw document to structured math problem."""

    def __init__(self, output_dir: Optional[Path] = None, state_manager: Optional[StateManager] = None) -> None:
        self.extractor = PDFExtractor(output_dir=output_dir)
        self.chunker = HeaderChunker()
        self.formalizer = Formalizer()
        self.state_manager = state_manager or StateManager()

    def process(self, pdf_path: Path) -> FormalizedProblem:
        """Run the full ingestion flow.
        
        Args:
            pdf_path: Path to the PDF file.
            
        Returns:
            FormalizedProblem extracted from the PDF.
            
        Raises:
            IngestionError: If any step fails.
        """
        try:
            # 0. Validate input
            logger.info("[1/4] Validating PDF...")
            validate_pdf(pdf_path)
            
            # 1. Extract text
            logger.info("[2/4] Extracting text from PDF...")
            try:
                md_text = self.extractor.extract(pdf_path)
            except PDFExtractionError as e:
                raise IngestionError(f"PDF extraction failed: {e}") from e
            
            if not md_text.strip():
                logger.warning("Extracted text is empty, may indicate scanned PDF")
            
            # 2. Chunk text
            logger.info("[3/4] Chunking text...")
            chunks = self.chunker.chunk(md_text)
            
            if not chunks:
                raise IngestionError("Text chunking produced no chunks")
            
            logger.info("Produced %d chunks", len(chunks))
            
            # 3. Formalize problem
            logger.info("[4/4] Formalizing problem...")
            source_doc = SourceDocument(
                format="pdf",
                uri=str(pdf_path),
                title=pdf_path.stem,
                extracted_text=md_text
            )
            
            try:
                problem = self.formalizer.formalize(chunks, source_doc=source_doc)
                # Save to persistent storage
                self.state_manager.save_problem(problem)
                return problem
            except FormalizationError as e:
                raise IngestionError(f"Problem formalization failed: {e}") from e
                
        except ValidationError as e:
            raise IngestionError(f"Validation failed: {e}") from e
        except Exception as e:
            raise IngestionError(f"Unexpected error during ingestion: {e}") from e
