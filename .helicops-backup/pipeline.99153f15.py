"""Ingestion pipeline: PDF -> Markdown -> Semantic Chunks -> FormalizedProblem."""

from pathlib import Path
from typing import Optional

from engine.state import FormalizedProblem, SourceDocument
from ingestion.chunking.semantic_chunker import SemanticChunker
from ingestion.extractors.pdf_extractor import PDFExtractor
from ingestion.formalization.formalizer import Formalizer


class IngestionPipeline:
    """Orchestrates the conversion from raw document to structured math problem."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.extractor = PDFExtractor(output_dir=output_dir)
        self.chunker = SemanticChunker()
        self.formalizer = Formalizer()

    def process(self, pdf_path: Path) -> FormalizedProblem:
        """Run the full ingestion flow."""
        # 1. Extract text
        md_text = self.extractor.extract(pdf_path)
        
        # 2. Chunk text
        chunks = self.chunker.chunk(md_text)
        
        # 3. Formalize problem
        source_doc = SourceDocument(
            format="pdf",
            uri=str(pdf_path),
            title=pdf_path.stem,
            extracted_text=md_text
        )
        
        return self.formalizer.formalize(chunks, source_doc=source_doc)
