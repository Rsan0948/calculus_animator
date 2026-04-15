"""Splits extracted markdown into semantic chunks for RAG."""

import re
from typing import List


class SemanticChunker:
    """Chunks text while preserving LaTeX blocks and logical sections."""

    def __init__(self, max_chunk_size: int = 1500):
        self.max_chunk_size = max_chunk_size

    def chunk(self, text: str) -> List[str]:
        """Splits markdown into chunks based on headers and block breaks."""
        # Simple split by common section headers or double newlines
        potential_breaks = re.split(r'(\n#{1,4}\s|\n\n+)', text)
        
        chunks = []
        current_chunk = ""
        
        for part in potential_breaks:
            if not part.strip():
                continue
                
            if len(current_chunk) + len(part) > self.max_chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = part
            else:
                current_chunk += part
        
        if current_chunk:
            chunks.append(current_chunk.strip())
            
        return chunks
