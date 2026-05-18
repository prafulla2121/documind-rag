"""
Query Intelligence Layer.
Processes raw user queries: intent detection, rewriting, filter extraction.
"""
import re
from dataclasses import dataclass, field
from typing import List


@dataclass
class ProcessedQuery:
    original: str
    rewritten: str
    intent: str  # "factual", "procedural", "comparison", "chitchat"
    filters: dict = field(default_factory=dict)
    expanded_terms: list = field(default_factory=list)
    should_use_multi_query: bool = False


class QueryProcessor:

    INTENT_PATTERNS = {
        "procedural": [r"how (do|can|to)", r"steps to", r"process for", r"procedure"],
        "factual": [r"what is", r"when (is|was|did)", r"who is", r"where is", r"tell me about"],
        "comparison": [r"vs", r"difference between", r"compare", r"better"],
        "chitchat": [r"hello|hi|hey", r"thanks|thank you", r"how are you", r"good morning"],
    }

    DEPARTMENT_KEYWORDS = {
        "HR": ["leave", "vacation", "salary", "payroll", "benefits", "employee", "hiring", "onboarding"],
        "IT": ["software", "laptop", "password", "vpn", "email", "account", "wifi", "network"],
        "Finance": ["budget", "expense", "reimbursement", "invoice", "payment", "tax"],
        "Legal": ["contract", "compliance", "policy", "nda", "agreement", "regulation"],
    }

    async def refine_async(self, query: str, llm_provider=None) -> ProcessedQuery:
        """
        Asynchronously process and refine the query using an LLM if available.
        Handles spelling corrections and expansion.
        """
        intent = self._detect_intent(query)
        filters = self._extract_filters(query)
        rewritten = self._rewrite(query)
        
        # If LLM is available, use it for spelling correction and normalization
        if llm_provider:
            try:
                refinement_prompt = f"""
                Rewrite the following user query to correct any spelling mistakes and make it more suitable for a semantic search engine.
                Keep the original intent and key entities intact.
                If the query is already perfect, just return it as is.
                ONLY return the rewritten query text.
                
                Query: {query}
                Rewritten:"""
                
                llm_rewritten = await llm_provider.generate([{"role": "user", "content": refinement_prompt}])
                rewritten = llm_rewritten.strip().strip('"').strip("'")
            except Exception:
                pass # Fallback to basic rewrite
                
        expanded = self._expand_terms(rewritten)

        return ProcessedQuery(
            original=query,
            rewritten=rewritten,
            intent=intent,
            filters=filters,
            expanded_terms=expanded,
            should_use_multi_query=(intent in ["factual", "procedural"] and len(query.split()) > 5),
        )

    def process(self, query: str) -> ProcessedQuery:
        """Synchronous version for fallback."""
        intent = self._detect_intent(query)
        filters = self._extract_filters(query)
        rewritten = self._rewrite(query)
        expanded = self._expand_terms(query)

        return ProcessedQuery(
            original=query,
            rewritten=rewritten,
            intent=intent,
            filters=filters,
            expanded_terms=expanded,
            should_use_multi_query=(intent in ["factual", "procedural"] and len(query.split()) > 5),
        )

    def _detect_intent(self, query: str) -> str:
        query_lower = query.lower()
        for intent, patterns in self.INTENT_PATTERNS.items():
            if any(re.search(p, query_lower) for p in patterns):
                return intent
        return "factual"

    def _extract_filters(self, query: str) -> dict:
        filters = {}
        query_lower = query.lower()
        for dept, keywords in self.DEPARTMENT_KEYWORDS.items():
            if any(kw in query_lower for kw in keywords):
                filters["department"] = dept
                break
        return filters

    def _rewrite(self, query: str) -> str:
        replacements = {
            "PTO": "paid time off",
            "OOO": "out of office",
            "WFH": "work from home",
            "EOD": "end of day",
            "ASAP": "as soon as possible",
        }
        result = query
        for abbr, expansion in replacements.items():
            result = re.sub(rf"\b{abbr}\b", expansion, result, flags=re.IGNORECASE)
        return result

    def _expand_terms(self, query: str) -> list:
        synonyms = {
            "policy": ["rule", "guideline", "procedure"],
            "employee": ["staff", "worker", "team member"],
            "request": ["apply", "submit", "ask"],
            "leave": ["time off", "absence", "vacation"],
        }
        terms = []
        for word in query.lower().split():
            if word in synonyms:
                terms.extend(synonyms[word])
        return terms
