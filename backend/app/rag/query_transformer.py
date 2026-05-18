"""
Query Transformer — HyDE, Multi-Query, Step-Back, and routing.
These techniques massively improve retrieval recall before hitting the vector store.
"""
import json
import logging
from typing import List

logger = logging.getLogger(__name__)


class QueryTransformer:
    """
    Transforms user queries using 4 techniques:
    1. HyDE        — Generate a hypothetical answer, embed that (better semantic match)
    2. Multi-Query — Generate N variants for broader coverage
    3. Step-Back   — Generate a more general version for background context
    4. Route       — Classify into semantic/keyword/hybrid/summary
    """

    def __init__(self, llm_provider):
        self.llm = llm_provider

    async def hyde(self, query: str) -> str:
        """
        Hypothetical Document Embedding:
        Generate a hypothetical answer passage and embed it.
        Answers are closer in embedding space to real document chunks than queries.
        """
        prompt = f"""Write a short passage (2–3 sentences) that would directly answer 
the following question. Write as an expert. Do NOT say 'I don't know'.

Question: {query}

Hypothetical answer passage:"""
        try:
            result = await self.llm.generate([{"role": "user", "content": prompt}])
            logger.debug(f"HyDE generated for: {query[:50]}")
            return result.strip()
        except Exception as e:
            logger.warning(f"HyDE failed, using original query: {e}")
            return query

    async def multi_query(self, query: str, n: int = 3) -> List[str]:
        """
        Generate N rephrasings of the original query.
        Different phrasings hit different parts of the document embedding space.
        """
        prompt = f"""Generate {n} different versions of this question for vector database retrieval.
Return ONLY a JSON array of strings. No explanation, no markdown.

Original question: {query}

JSON array of {n} variants:"""
        try:
            result = await self.llm.generate([{"role": "user", "content": prompt}])
            # Strip markdown code blocks if model adds them
            cleaned = result.strip().strip("```json").strip("```").strip()
            queries = json.loads(cleaned)
            if isinstance(queries, list):
                logger.debug(f"Multi-query generated {len(queries)} variants")
                return [q for q in queries if isinstance(q, str)]
        except Exception as e:
            logger.warning(f"Multi-query failed: {e}")
        return [query]

    async def step_back(self, query: str) -> str:
        """
        Generate a more general 'step-back' question to retrieve background context.
        """
        prompt = f"""Given a specific question, generate a more general background question 
that covers the broader topic. This helps retrieve foundational context.

Specific: {query}
General step-back question:"""
        try:
            result = await self.llm.generate([{"role": "user", "content": prompt}])
            return result.strip()
        except Exception as e:
            logger.warning(f"Step-back failed: {e}")
            return query

    async def route_query(self, query: str) -> str:
        """
        Classify the query to select retrieval strategy:
        - semantic  → conceptual, how/why questions
        - keyword   → exact names, IDs, numbers
        - hybrid    → mixed (default safe choice)
        - summary   → wants a document overview
        """
        prompt = f"""Classify this query into exactly one of: semantic, keyword, hybrid, summary.
- semantic: "how does X work?", "explain Y", "what is Z?"
- keyword:  "what is the value of X?", "list all Y", specific names or codes
- hybrid:   needs both conceptual and exact retrieval
- summary:  "summarize the document", "give an overview"

Query: {query}
Classification (one word only):"""
        try:
            result = await self.llm.generate([{"role": "user", "content": prompt}])
            route = result.strip().lower().split()[0]
            if route in ["semantic", "keyword", "hybrid", "summary"]:
                return route
        except Exception as e:
            logger.warning(f"Query routing failed: {e}")
        return "hybrid"
