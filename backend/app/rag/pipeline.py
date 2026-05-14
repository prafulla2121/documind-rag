"""
RAG Pipeline Orchestrator — wires all phases together.
Input → QueryProcessor → HybridRetriever → Reranker → ContextBuilder → LLM → Output
"""
import time
import json
import logging
from typing import AsyncGenerator

from app.rag.query_processor import QueryProcessor
from app.rag.retriever import HybridRetriever
from app.rag.reranker import Reranker
from app.rag.context_builder import ContextBuilder
from app.rag.llm_client import OllamaClient
from app.rag.prompts import (
    RAG_SYSTEM_PROMPT, RAG_QUERY_TEMPLATE,
    FALLBACK_RESPONSE, CHITCHAT_RESPONSE,
)
from app.storage.cache import CacheManager
from app.core.config import settings

logger = logging.getLogger(__name__)


class RAGPipeline:

    def __init__(
        self,
        query_processor: QueryProcessor,
        retriever: HybridRetriever,
        reranker: Reranker,
        context_builder: ContextBuilder,
        llm_client: OllamaClient,
        cache: CacheManager,
    ):
        self.query_processor = query_processor
        self.retriever = retriever
        self.reranker = reranker
        self.context_builder = context_builder
        self.llm = llm_client
        self.cache = cache

    async def query(
        self,
        user_query: str,
        user_id: str = "anonymous",
        history: list = None,
        filters: dict | None = None,
    ) -> dict:
        start_time = time.time()
        stage_start = time.time()
        stage_timings = {}
        
        history_context = self._format_history(history)

        # 0. Check response cache
        cached = await self.cache.get_response(
            user_query,
            user_id=user_id,
            filters=filters,
            model_id=settings.LLM_MODEL,
        )
        if cached:
            return {**cached, "from_cache": True}
        stage_timings["cache_lookup_ms"] = int((time.time() - stage_start) * 1000)

        # 1. Process query
        stage_start = time.time()
        processed = self.query_processor.process(user_query)
        stage_timings["query_processing_ms"] = int((time.time() - stage_start) * 1000)

        # Bail early for chitchat
        if processed.intent == "chitchat":
            return {
                "answer": CHITCHAT_RESPONSE,
                "sources": [],
                "intent": "chitchat",
                "query_rewritten": processed.rewritten,
                "chunks_retrieved": 0,
                "chunks_after_rerank": 0,
                "latency_ms": int((time.time() - start_time) * 1000),
                "from_cache": False,
            }

        # 2. Retrieve
        stage_start = time.time()
        # Combine user filters, processor filters, and add user_id isolation
        search_filters = filters.copy() if filters else {}
        if processed.filters:
            search_filters.update(processed.filters)
        search_filters["user_id"] = user_id

        candidates = self.retriever.retrieve(
            query=processed.rewritten,
            top_k=10,
            filters=search_filters,
        )
        stage_timings["retrieval_ms"] = int((time.time() - stage_start) * 1000)

        if not candidates:
            return {
                "answer": FALLBACK_RESPONSE,
                "sources": [],
                "intent": processed.intent,
                "query_rewritten": processed.rewritten,
                "chunks_retrieved": 0,
                "chunks_after_rerank": 0,
                "latency_ms": int((time.time() - start_time) * 1000),
                "from_cache": False,
            }

        # 3. Rerank
        stage_start = time.time()
        reranked = self.reranker.rerank(
            query=processed.rewritten,
            candidates=candidates,
        )
        stage_timings["rerank_ms"] = int((time.time() - stage_start) * 1000)

        # 4. Build context
        stage_start = time.time()
        context, sources = self.context_builder.build(reranked, user_query)
        stage_timings["context_build_ms"] = int((time.time() - stage_start) * 1000)

        # 5. Generate answer
        stage_start = time.time()
        prompt = RAG_QUERY_TEMPLATE.format(context=context, query=user_query)
        if history_context:
            prompt = f"PREVIOUS CHAT HISTORY:\n{history_context}\n\n{prompt}"

        answer = await self.llm.generate(
            prompt=prompt,
            system_prompt=RAG_SYSTEM_PROMPT,
            temperature=0.1,
        )
        stage_timings["generation_ms"] = int((time.time() - stage_start) * 1000)

        result = {
            "answer": answer,
            "sources": sources,
            "intent": processed.intent,
            "query_rewritten": processed.rewritten,
            "chunks_retrieved": len(candidates),
            "chunks_after_rerank": len(reranked),
            "latency_ms": int((time.time() - start_time) * 1000),
            "stage_timings": stage_timings,
            "from_cache": False,
        }

        # 6. Cache response
        await self.cache.set_response(
            user_query,
            result,
            user_id=user_id,
            filters=filters,
            model_id=settings.LLM_MODEL,
        )

        return result

    async def stream_query(
        self,
        user_query: str,
        user_id: str = "anonymous",
        history: list = None,
        filters: dict | None = None,
    ) -> AsyncGenerator:
        """Streaming version — yields SSE events for real-time frontend."""

        history_context = self._format_history(history)

        yield {"type": "phase", "data": "analyzing_query"}
        # 1. Process query
        processed = self.query_processor.process(user_query)

        if processed.intent == "chitchat":
            yield {"type": "sources", "data": []}
            yield {"type": "token", "data": CHITCHAT_RESPONSE}
            yield {"type": "done", "data": None}
            return

        # 2. Retrieve
        yield {"type": "phase", "data": "retrieving_documents"}
        search_filters = filters.copy() if filters else {}
        if processed.filters:
            search_filters.update(processed.filters)
        search_filters["user_id"] = user_id

        candidates = self.retriever.retrieve(
            query=processed.rewritten,
            top_k=10,
            filters=search_filters,
        )

        if not candidates:
            yield {"type": "sources", "data": []}
            yield {"type": "token", "data": FALLBACK_RESPONSE}
            yield {"type": "done", "data": None}
            return

        # 3. Rerank
        yield {"type": "phase", "data": "reranking_results"}
        reranked = self.reranker.rerank(processed.rewritten, candidates)

        # 4. Build context
        yield {"type": "phase", "data": "building_context"}
        context, sources = self.context_builder.build(reranked, user_query)

        # Yield sources first (UI shows them while text streams)
        yield {"type": "sources", "data": sources}

        # 5. Stream the answer
        yield {"type": "phase", "data": "drafting_answer"}
        prompt = RAG_QUERY_TEMPLATE.format(context=context, query=user_query)
        if history_context:
            prompt = f"PREVIOUS CHAT HISTORY:\n{history_context}\n\n{prompt}"

        async for token in self.llm.stream_generate(prompt, RAG_SYSTEM_PROMPT):
            yield {"type": "token", "data": token}

        yield {"type": "done", "data": None}
        
    def _format_history(self, history: list) -> str:
        if not history:
            return ""
        
        # Take last 5 messages to save tokens
        recent = history[-5:] if len(history) > 5 else history
        formatted = []
        for msg in recent:
            role = "USER" if msg["role"] == "user" else "ASSISTANT"
            # Ignore messages that are sources lists or empty
            content = msg["content"].strip()
            if content:
                formatted.append(f"{role}: {content}")
                
        return "\n".join(formatted)
