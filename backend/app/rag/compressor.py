import nltk
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class ContextCompressor:
    """
    Compresses retrieved context by selecting only the most relevant sentences.
    Reduces token usage and noise.
    """

    def __init__(self, top_n_sentences: int = 5):
        self.top_n_sentences = top_n_sentences
        try:
            nltk.download('punkt', quiet=True)
        except Exception:
            pass

    def compress(self, query: str, context_chunks: List[Dict[str, Any]]) -> str:
        """
        Simple sentence-level relevance compression.
        """
        if not context_chunks:
            return ""

        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        all_sentences = []
        for chunk in context_chunks:
            text = chunk.get("text", "")
            sentences = nltk.sent_tokenize(text)
            all_sentences.extend(sentences)

        if not all_sentences:
            return ""

        # Calculate similarity of each sentence to the query
        try:
            vectorizer = TfidfVectorizer().fit_transform(all_sentences + [query])
            vectors = vectorizer.toarray()

            query_vector = vectors[-1].reshape(1, -1)
            sentence_vectors = vectors[:-1]

            similarities = cosine_similarity(query_vector, sentence_vectors).flatten()

            # Get top N sentences
            top_indices = similarities.argsort()[-self.top_n_sentences:][::-1]
            # Maintain original order
            top_indices.sort()

            compressed_context = " ".join([all_sentences[i] for i in top_indices])
            return compressed_context
        except Exception as e:
            logger.warning(f"Context compression failed: {e}")
            # Fallback to just joining chunks
            return " ".join([c.get("text", "") for c in context_chunks])
