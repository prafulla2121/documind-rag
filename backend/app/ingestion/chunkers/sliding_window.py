"""
Recursive Character Chunker.
Splits text by a list of separators (e.g. \n\n, \n, " ", "") to find the best cut points.
Industry standard for RAG.
"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class Chunk:
    text: str
    chunk_index: int
    start_char: int = 0
    end_char: int = 0
    metadata: dict = field(default_factory=dict)


class SlidingWindowChunker:
    """
    Renamed conceptually to SlidingWindow but implementing Recursive behavior
    for better semantic boundaries.
    """

    def __init__(self, chunk_size: int = 512, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.separators = ["\n\n", "\n", ". ", " ", ""]

    def chunk(self, text: str, base_metadata: dict = None) -> List[Chunk]:
        if not text:
            return []
        
        if base_metadata is None:
            base_metadata = {}

        # Recursive splitting logic
        raw_chunks = self._recursive_split(text, self.separators)
        
        # Combine small chunks into larger ones up to chunk_size
        final_chunks = []
        current_text = ""
        current_start = 0
        
        for i, part in enumerate(raw_chunks):
            if len(current_text) + len(part) <= self.chunk_size:
                current_text += part
            else:
                if current_text:
                    final_chunks.append(Chunk(
                        text=current_text.strip(),
                        chunk_index=len(final_chunks),
                        start_char=current_start,
                        end_char=current_start + len(current_text),
                        metadata={**base_metadata, "chunk_method": "recursive"},
                    ))
                    # Handle overlap
                    overlap_size = min(self.overlap, len(current_text))
                    overlap_text = current_text[-overlap_size:]
                    current_text = overlap_text + part
                    current_start += len(current_text) - overlap_size
                else:
                    # Single part larger than chunk_size
                    final_chunks.append(Chunk(
                        text=part[:self.chunk_size],
                        chunk_index=len(final_chunks),
                        metadata=base_metadata
                    ))
        
        if current_text.strip():
            final_chunks.append(Chunk(
                text=current_text.strip(),
                chunk_index=len(final_chunks),
                metadata=base_metadata
            ))

        return final_chunks

    def _recursive_split(self, text: str, separators: List[str]) -> List[str]:
        if not separators:
            return [text]
        
        separator = separators[0]
        new_separators = separators[1:]
        
        parts = text.split(separator)
        final_parts = []
        
        for i, part in enumerate(parts):
            # Re-add the separator except for the last part
            if i < len(parts) - 1:
                part += separator
                
            if len(part) <= self.chunk_size:
                final_parts.append(part)
            else:
                final_parts.extend(self._recursive_split(part, new_separators))
        
        return final_parts
