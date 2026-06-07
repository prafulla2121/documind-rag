import numpy as np
import logging
from typing import List, Dict, Any
from app.ingestion.chunkers.sliding_window import Chunk
from app.core.config import settings

logger = logging.getLogger(__name__)

class SemanticChunker:
    """
    Splits text into chunks based on semantic similarity.
    Uses sentence embeddings to identify topic shifts.
    """
    def __init__(self, buffer_size: int = 1, breakpoint_percentile: float = 95):
        self.buffer_size = buffer_size
        self.breakpoint_percentile = breakpoint_percentile
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(settings.EMBEDDING_MODEL)
        except ImportError:
            logger.error("sentence-transformers not installed. SemanticChunking disabled.")
            self.model = None

    def chunk(self, text: str, metadata: Dict[str, Any]) -> List[Chunk]:
        if not self.model or not text.strip():
            return []

        import nltk
        nltk.download('punkt', quiet=True)
        sentences = nltk.sent_tokenize(text)
        if len(sentences) <= 1:
            return [Chunk(text=text, metadata=metadata, chunk_index=0)]

        # 1. Embed sentences
        embeddings = self.model.encode(sentences)

        # 2. Calculate distances between adjacent sentences
        distances = []
        for i in range(len(embeddings) - 1):
            similarity = np.dot(embeddings[i], embeddings[i+1]) / (np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[i+1]))
            distances.append(1 - similarity)

        # 3. Identify breakpoints
        if not distances:
            return [Chunk(text=text, metadata=metadata, chunk_index=0)]

        breakpoint_threshold = np.percentile(distances, self.breakpoint_percentile)
        breakpoints = [i for i, x in enumerate(distances) if x > breakpoint_threshold]

        # 4. Create chunks
        chunks = []
        start_idx = 0
        for i, bp in enumerate(breakpoints):
            chunk_text = " ".join(sentences[start_idx:bp+1])
            chunks.append(Chunk(
                text=chunk_text,
                metadata={**metadata, "chunk_index": i},
                chunk_index=i
            ))
            start_idx = bp + 1

        # Last chunk
        if start_idx < len(sentences):
            chunk_text = " ".join(sentences[start_idx:])
            chunks.append(Chunk(
                text=chunk_text,
                metadata={**metadata, "chunk_index": len(chunks)},
                chunk_index=len(chunks)
            ))

        return chunks
