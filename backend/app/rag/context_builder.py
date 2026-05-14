"""
Context Builder — assembles retrieved chunks into coherent context for the LLM.
Deduplicates, orders by relevance, respects token budget, adds source citations.
"""
from typing import List, Dict, Tuple


class ContextBuilder:

    MAX_CONTEXT_TOKENS = 3000
    AVG_CHARS_PER_TOKEN = 4
    MAX_CONTEXT_CHARS = MAX_CONTEXT_TOKENS * AVG_CHARS_PER_TOKEN

    def build(self, chunks: List[Dict], query: str) -> Tuple[str, List[Dict]]:
        """
        Returns: (formatted_context_string, list_of_sources)
        """
        # Deduplicate
        chunks = self._deduplicate(chunks)

        context_parts = []
        sources = []
        char_count = 0

        for i, chunk in enumerate(chunks, 1):
            chunk_text = chunk["text"]
            formatted = f"--- DOCUMENT {i} ---\n{chunk_text}\n"

            if char_count + len(formatted) > self.MAX_CONTEXT_CHARS:
                break

            context_parts.append(formatted)
            char_count += len(formatted)

            metadata = chunk.get("metadata", {})
            title = metadata.get("title", "Unknown")
            
            # Only add to sources if title not already present
            if not any(s["title"] == title for s in sources):
                sources.append({
                    "index": i,
                    "title": title,
                    "filename": metadata.get("filename", ""),
                    "source_type": metadata.get("source_type", ""),
                    "url": metadata.get("source_url", ""),
                    "section": metadata.get("section_heading", ""),
                    "score": chunk.get("rerank_score", chunk.get("rrf_score", 0)),
                    "retrieval_methods": chunk.get("retrieval_methods", []),
                    "excerpt": chunk_text[:240],
                })

        context = "\n---\n".join(context_parts)
        return context, sources

    def _deduplicate(self, chunks: List[Dict]) -> List[Dict]:
        """Remove chunks with >80% text overlap."""
        seen = []
        unique = []

        for chunk in chunks:
            text = chunk["text"]
            is_duplicate = False

            for seen_text in seen:
                overlap = self._overlap_ratio(text, seen_text)
                if overlap > 0.8:
                    is_duplicate = True
                    break

            if not is_duplicate:
                seen.append(text)
                unique.append(chunk)

        return unique

    def _overlap_ratio(self, text1: str, text2: str) -> float:
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        return len(intersection) / min(len(words1), len(words2))
