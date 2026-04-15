"""Splits extracted markdown into chunks based on headers and paragraph breaks.

This is NOT semantic chunking (which uses embeddings or semantic similarity).
For true semantic chunking, use a separate implementation with vector embeddings.
"""

import re
from typing import List


class HeaderChunker:
    """Chunks text by markdown headers and paragraph breaks."""

    def __init__(self, max_chunk_size: int = 1500) -> None:
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
