"""
Structural Chunker.
Splits by document headings/sections first, then applies sliding window on long sections.
BEST FOR: Company docs, PDFs, wiki pages, manuals.
"""
import re
from typing import List
from .sliding_window import Chunk, SlidingWindowChunker


class StructuralChunker:

    HEADING_PATTERNS = [
        r"^#+\s+.+$",                # Markdown headings
        r"^[A-Z][^.!?]*:\s*$",       # Sentence-case headings ending in :
        r"^\d+(\.\d+)*\s+[A-Z].+$",  # Numbered sections (1., 1.1, 1.1.1)
        r"^[A-Z\s]{5,}\n?$",         # ALL CAPS HEADERS
        r"^(Section|Chapter)\s+\d+.+$", # Section/Chapter headers
    ]

    def __init__(self, max_chunk_size: int = 1000, overlap: int = 50):
        self.max_chunk_size = max_chunk_size
        self.fallback_chunker = SlidingWindowChunker(
            chunk_size=max_chunk_size,
            overlap=overlap,
        )

    def chunk(self, text: str, base_metadata: dict = None) -> List[Chunk]:
        if base_metadata is None:
            base_metadata = {}

        sections = self._split_by_headings(text)
        all_chunks = []
        global_idx = 0

        for section in sections:
            heading = section.get("heading", "")
            content = section["content"]

            if not content.strip():
                continue

            section_metadata = {
                **base_metadata,
                "section_heading": heading,
                "chunk_method": "structural",
            }

            if len(content) <= self.max_chunk_size:
                chunk_text = f"{heading}\n\n{content}".strip() if heading else content
                all_chunks.append(Chunk(
                    text=chunk_text,
                    chunk_index=global_idx,
                    start_char=0,
                    end_char=len(content),
                    metadata=section_metadata,
                ))
                global_idx += 1
            else:
                sub_chunks = self.fallback_chunker.chunk(content, section_metadata)
                for chunk in sub_chunks:
                    if heading:
                        chunk.text = f"[Section: {heading}]\n{chunk.text}"
                    chunk.chunk_index = global_idx
                    all_chunks.append(chunk)
                    global_idx += 1

        return all_chunks

    def _split_by_headings(self, text: str) -> list:
        lines = text.split("\n")
        sections = []
        current_heading = ""
        current_content = []

        for line in lines:
            if self._is_heading(line):
                if current_content:
                    sections.append({
                        "heading": current_heading,
                        "content": "\n".join(current_content).strip(),
                    })
                current_heading = line.strip()
                current_content = []
            else:
                current_content.append(line)

        if current_content:
            sections.append({
                "heading": current_heading,
                "content": "\n".join(current_content).strip(),
            })

        return sections

    def _is_heading(self, line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return False
        return any(re.match(pat, stripped) for pat in self.HEADING_PATTERNS)
