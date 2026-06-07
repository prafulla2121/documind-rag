import logging
from typing import List
from app.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)

class QueryTransformer:
    """
    Transforms user queries for better retrieval.
    Includes HyDE (Hypothetical Document Embedding) and Multi-Query expansion.
    """

    async def hyde(self, query: str, llm: BaseLLMProvider) -> str:
        """Generate a hypothetical answer to the query."""
        prompt = f"Please write a scientific-sounding paragraph that answers the following question: {query}"
        hypothetical_answer = await llm.generate([{"role": "user", "content": prompt}])
        return hypothetical_answer

    async def multi_query(self, query: str, llm: BaseLLMProvider) -> List[str]:
        """Generate multiple versions of the query to improve recall."""
        prompt = f"Provide 3 different versions of the following search query to help retrieve more relevant documents: {query}. Respond with only the queries, one per line."
        response = await llm.generate([{"role": "user", "content": prompt}])
        queries = [q.strip() for q in response.split("\n") if q.strip()]
        return queries[:3]
