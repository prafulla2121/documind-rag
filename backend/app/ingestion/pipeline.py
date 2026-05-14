"""
Ingestion Pipeline — orchestrates the full document ingestion flow:
Source → Parse → Clean → Chunk → Embed → Store
"""
import hashlib
import uuid
import os
import logging
from pathlib import Path

from app.ingestion.parsers.pdf_parser import PDFParser
from app.ingestion.parsers.html_parser import HTMLParser
from app.ingestion.parsers.docx_parser import DOCXParser
from app.ingestion.cleaner import TextCleaner
from app.ingestion.chunkers.structural import StructuralChunker
from app.ingestion.chunkers.sliding_window import SlidingWindowChunker
from app.ingestion.embedder import Embedder
from app.storage.vector_store import VectorStore
from app.core.config import settings

logger = logging.getLogger(__name__)


class IngestionPipeline:

    def __init__(self):
        self.pdf_parser = PDFParser()
        self.html_parser = HTMLParser()
        self.docx_parser = DOCXParser()
        self.cleaner = TextCleaner()
        self.structural_chunker = StructuralChunker(
            max_chunk_size=settings.CHUNK_SIZE,
            overlap=settings.CHUNK_OVERLAP,
        )
        self.sliding_chunker = SlidingWindowChunker(
            chunk_size=settings.CHUNK_SIZE,
            overlap=settings.CHUNK_OVERLAP,
        )
        self.embedder = Embedder(model_name=settings.EMBEDDING_MODEL)
        self.vector_store = VectorStore()

    def ingest_file(self, filepath: str, original_filename: str = "", user_id: str = "anonymous") -> dict:
        """
        Ingest a single file: parse → clean → chunk → embed → store.
        Returns dict with doc_id and num_chunks.
        """
        filepath = str(filepath)
        if not original_filename:
            original_filename = Path(filepath).name

        ext = Path(filepath).suffix.lower()
        doc_id = str(uuid.uuid4())

        logger.info(f"Ingesting: {original_filename} (type: {ext})")

        # 1. Parse
        parsed = self._parse_file(filepath, ext)
        if not parsed or not parsed.get("full_text", "").strip():
            logger.warning(f"No text extracted from {original_filename}")
            return {"doc_id": doc_id, "num_chunks": 0, "status": "empty"}

        full_text = parsed["full_text"]
        title = original_filename if original_filename else parsed.get("title", "Unknown Document")

        # 2. Deduplication check via content hash
        content_hash = hashlib.md5(full_text.encode()).hexdigest()

        # 3. Clean
        source_type = self._ext_to_source_type(ext)
        cleaned_text = self.cleaner.clean(full_text, source_type)

        if not cleaned_text.strip():
            return {"doc_id": doc_id, "num_chunks": 0, "status": "empty_after_clean"}

        # 4. Chunk
        base_metadata = {
            "doc_id": doc_id,
            "source_type": source_type,
            "title": title,
            "filename": original_filename,
            "source_url": "",
            "user_id": user_id,
        }

        # Use structural chunker for docs with headings, sliding window as fallback
        chunks = self.structural_chunker.chunk(cleaned_text, base_metadata)
        if not chunks:
            chunks = self.sliding_chunker.chunk(cleaned_text, base_metadata)

        if not chunks:
            return {"doc_id": doc_id, "num_chunks": 0, "status": "no_chunks"}

        logger.info(f"Created {len(chunks)} chunks from {original_filename}")

        # 5. Embed
        texts = [c.text for c in chunks]
        embeddings = self.embedder.embed_documents(texts, batch_size=settings.EMBEDDING_BATCH_SIZE)

        # 6. Store in vector DB
        self.vector_store.create_collection(vector_dim=self.embedder.dimension)
        self.vector_store.upsert_chunks(chunks, embeddings)

        logger.info(f"✅ Ingested {original_filename}: {len(chunks)} chunks stored")

        return {
            "doc_id": doc_id,
            "num_chunks": len(chunks),
            "content_hash": content_hash,
            "title": title,
            "status": "completed",
        }

    def ingest_text(self, text: str, title: str = "Manual Input", source_type: str = "text", user_id: str = "anonymous") -> dict:
        """Ingest raw text directly."""
        doc_id = str(uuid.uuid4())
        cleaned = self.cleaner.clean(text, source_type)

        base_metadata = {
            "doc_id": doc_id,
            "source_type": source_type,
            "title": title,
            "filename": "",
            "source_url": "",
            "user_id": user_id,
        }

        chunks = self.structural_chunker.chunk(cleaned, base_metadata)
        if not chunks:
            chunks = self.sliding_chunker.chunk(cleaned, base_metadata)

        if not chunks:
            return {"doc_id": doc_id, "num_chunks": 0, "status": "no_chunks"}

        texts = [c.text for c in chunks]
        embeddings = self.embedder.embed_documents(texts)

        self.vector_store.create_collection(vector_dim=self.embedder.dimension)
        self.vector_store.upsert_chunks(chunks, embeddings)

        return {
            "doc_id": doc_id,
            "num_chunks": len(chunks),
            "title": title,
            "status": "completed",
        }

    def _parse_file(self, filepath: str, ext: str) -> dict | None:
        try:
            if ext == ".pdf":
                return self.pdf_parser.parse(filepath)
            elif ext == ".docx":
                return self.docx_parser.parse(filepath)
            elif ext in (".html", ".htm"):
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    html_content = f.read()
                return self.html_parser.parse(html_content)
            elif ext in (".txt", ".md", ".csv"):
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                return {"full_text": content, "title": Path(filepath).stem}
            else:
                logger.warning(f"Unsupported file type: {ext}")
                return None
        except Exception as e:
            logger.error(f"Parse error for {filepath}: {e}")
            return None

    def _ext_to_source_type(self, ext: str) -> str:
        mapping = {
            ".pdf": "pdf",
            ".docx": "docx",
            ".html": "web",
            ".htm": "web",
            ".txt": "text",
            ".md": "text",
            ".csv": "text",
        }
        return mapping.get(ext, "unknown")
