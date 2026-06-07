# 🏭 Production-Grade RAG Company Assistant — Complete Blueprint
> **Zero Budget. Real Architecture. Portfolio-Ready.**
> A complete, opinionated guide to building a real-world RAG system using 100% free and open-source tools.

---

## 📋 Table of Contents

1. [System Philosophy](#system-philosophy)
2. [Architecture Overview](#architecture-overview)
3. [Tech Stack Decision Matrix](#tech-stack-decision-matrix)
4. [Phase 0 — Project Setup & DevOps](#phase-0--project-setup--devops)
5. [Phase 1 — Data Sourcing & Web Scraping](#phase-1--data-sourcing--web-scraping)
6. [Phase 2 — Data Ingestion Pipeline](#phase-2--data-ingestion-pipeline)
7. [Phase 3 — Chunking Engine](#phase-3--chunking-engine)
8. [Phase 4 — Embeddings](#phase-4--embeddings)
9. [Phase 5 — Vector Database](#phase-5--vector-database)
10. [Phase 6 — Retrieval Engine](#phase-6--retrieval-engine)
11. [Phase 7 — Reranking](#phase-7--reranking)
12. [Phase 8 — Query Intelligence Layer](#phase-8--query-intelligence-layer)
13. [Phase 9 — LLM & Context Engineering](#phase-9--llm--context-engineering)
14. [Phase 10 — RAG Core Orchestration](#phase-10--rag-core-orchestration)
15. [Phase 11 — Backend API](#phase-11--backend-api)
16. [Phase 12 — Frontend](#phase-12--frontend)
17. [Phase 13 — Async Pipeline & Queue](#phase-13--async-pipeline--queue)
18. [Phase 14 — Caching Layer](#phase-14--caching-layer)
19. [Phase 15 — Evaluation & Observability](#phase-15--evaluation--observability)
20. [Phase 16 — Auth & Multi-User](#phase-16--auth--multi-user)
21. [Phase 17 — Scaling Strategy](#phase-17--scaling-strategy)
22. [Complete Folder Structure](#complete-folder-structure)
23. [Data Flow Diagrams](#data-flow-diagrams)
24. [The Master Prompt Collection](#the-master-prompt-collection)
25. [Portfolio Presentation Guide](#portfolio-presentation-guide)

---

## System Philosophy

### Why Most RAG Systems Fail in Production

Most tutorials build a "demo RAG" — embed some docs, call an LLM, show an answer. That's not a system. That's a proof of concept. A real company assistant needs to handle:

- **Dirty data** — inconsistent formats, broken PDFs, HTML noise
- **Diverse queries** — vague questions, multi-hop reasoning, negations
- **Scale** — thousands of documents, concurrent users
- **Trust** — grounded answers, source citations, no hallucination
- **Observability** — you must know *why* it gave a wrong answer

### Our Design Principles

| Principle | What It Means |
|-----------|---------------|
| **Retrieval > Generation** | A great retriever with a weak LLM beats a great LLM with weak retrieval |
| **Eval-First** | Never build a feature you can't measure |
| **Modularity** | Every component must be swappable |
| **Fail Gracefully** | Return "I don't know" rather than hallucinate |
| **Free Stack** | No paid APIs at core; free-tier integrations only where needed |

---

## Architecture Overview

### 30,000 ft View

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER INTERFACE                                │
│              Next.js Frontend  ←→  FastAPI Backend                  │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                     ┌──────▼──────┐
                     │  API LAYER  │
                     │  FastAPI    │
                     └──────┬──────┘
                            │
          ┌─────────────────▼──────────────────┐
          │         RAG ORCHESTRATOR            │
          │  LangChain / Custom Pipeline        │
          └──┬──────────┬───────────┬───────────┘
             │          │           │
    ┌────────▼──┐  ┌────▼────┐  ┌──▼────────┐
    │  QUERY    │  │RETRIEVAL│  │  LLM      │
    │INTELLIGENCE│  │ ENGINE  │  │ ENGINE    │
    │  Layer    │  │         │  │ Ollama    │
    └───────────┘  └────┬────┘  └───────────┘
                        │
          ┌─────────────▼──────────────────┐
          │          VECTOR DB              │
          │     Qdrant (self-hosted)        │
          └────────────────────────────────┘
                        │
          ┌─────────────▼──────────────────┐
          │         DATA LAYER              │
          │  Ingestion → Chunk → Embed      │
          └────────────────────────────────┘
```

### The Three Engines (Mental Model)

```
ENGINE 1: DATA ENGINE
  Sources → Scraper → Parser → Cleaner → Chunker → Embedder → Vector DB

ENGINE 2: RETRIEVAL ENGINE  
  Query → Rewrite → [Dense + Sparse] Search → Merge → Rerank → Top K

ENGINE 3: REASONING ENGINE
  Context → Prompt Builder → LLM → Grounded Answer → Response
```

---

## Tech Stack Decision Matrix

### Why These Tools (Free-Only Stack)

| Layer | Chosen Tool | Why | Rejected Alternative | Rejection Reason |
|-------|-------------|-----|----------------------|------------------|
| **LLM** | Ollama (Mistral 7B / LLaMA 3.1 8B) | Local, free, fast | OpenAI GPT-4 | Paid API |
| **Embeddings** | `sentence-transformers` (BGE-M3) | Best free multilingual | OpenAI Embeddings | Paid |
| **Vector DB** | Qdrant (Docker) | Filtering, fast, production-ready | Pinecone | Paid beyond free tier |
| **BM25** | `rank_bm25` | Lightweight, pure Python | Elasticsearch | Heavy infra |
| **Reranker** | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Free, excellent quality | Cohere Rerank | Paid |
| **Backend** | FastAPI | Async, auto-docs, Python native | Django | Too heavy for APIs |
| **Frontend** | Next.js 14 (App Router) | SSR, streaming support | React SPA | No streaming UX |
| **Queue** | Celery + Redis (Docker) | Battle-tested, free | AWS SQS | Paid |
| **Cache** | Redis | Multi-purpose (queue + cache) | Memcached | Less versatile |
| **Scraping** | Scrapy + Playwright | Free, handles JS | Firecrawl | Paid for scale |
| **Parsing** | PyMuPDF + python-docx | Best free PDF/DOCX | Adobe API | Paid |
| **Observability** | Prometheus + Grafana (Docker) | Free, standard | DataDog | Paid |
| **Auth** | FastAPI + PyJWT | Zero cost | Auth0 | Paid beyond free tier |
| **Database** | PostgreSQL (Docker) | Metadata, users, eval logs | MongoDB | Overkill for structured |
| **Orchestration** | LangChain (custom pipeline) | Modular, battle-tested | LlamaIndex | Less flexible at low level |

---

## Phase 0 — Project Setup & DevOps

### 0.1 Folder Structure (Set Up First)

```
rag-company-assistant/
│
├── docker-compose.yml          # Spins up ALL infrastructure
├── .env.example
├── README.md
│
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI entry point
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── query.py
│   │   │   │   ├── ingest.py
│   │   │   │   └── admin.py
│   │   │   └── dependencies.py
│   │   ├── core/
│   │   │   ├── config.py       # All settings via Pydantic BaseSettings
│   │   │   ├── security.py     # JWT auth
│   │   │   └── logging.py
│   │   ├── rag/
│   │   │   ├── pipeline.py     # RAG orchestrator
│   │   │   ├── retriever.py    # Hybrid retrieval
│   │   │   ├── reranker.py
│   │   │   ├── query_processor.py
│   │   │   ├── context_builder.py
│   │   │   └── llm_client.py
│   │   ├── ingestion/
│   │   │   ├── scrapers/
│   │   │   │   ├── playwright_scraper.py
│   │   │   │   └── scrapy_spider.py
│   │   │   ├── parsers/
│   │   │   │   ├── pdf_parser.py
│   │   │   │   ├── docx_parser.py
│   │   │   │   ├── html_parser.py
│   │   │   │   └── base_parser.py
│   │   │   ├── chunkers/
│   │   │   │   ├── semantic_chunker.py
│   │   │   │   ├── structural_chunker.py
│   │   │   │   ├── sliding_window_chunker.py
│   │   │   │   └── hierarchical_chunker.py
│   │   │   ├── embedder.py
│   │   │   └── pipeline.py     # Ingestion orchestrator
│   │   ├── storage/
│   │   │   ├── vector_store.py # Qdrant client
│   │   │   ├── metadata_db.py  # PostgreSQL client
│   │   │   └── cache.py        # Redis client
│   │   ├── evaluation/
│   │   │   ├── metrics.py
│   │   │   ├── ragas_eval.py
│   │   │   └── logging.py
│   │   ├── workers/
│   │   │   ├── celery_app.py
│   │   │   └── tasks.py
│   │   └── models/             # Pydantic schemas
│   │       ├── query.py
│   │       ├── document.py
│   │       └── user.py
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/
│   ├── app/
│   │   ├── page.tsx            # Chat interface
│   │   ├── admin/page.tsx      # Admin dashboard
│   │   └── layout.tsx
│   ├── components/
│   │   ├── ChatWindow.tsx
│   │   ├── MessageBubble.tsx
│   │   ├── SourceCitation.tsx
│   │   ├── UploadZone.tsx
│   │   └── StatusIndicator.tsx
│   ├── lib/
│   │   └── api.ts
│   └── Dockerfile
│
├── scraping/
│   ├── scrapy_project/
│   └── playwright_scripts/
│
├── evaluation/
│   ├── datasets/               # Golden QA pairs
│   └── notebooks/
│
├── infra/
│   ├── prometheus/
│   │   └── prometheus.yml
│   └── grafana/
│       └── dashboards/
│
└── scripts/
    ├── seed_data.py
    ├── run_eval.py
    └── health_check.py
```

### 0.2 Docker Compose — One Command to Rule All Infrastructure

```yaml
# docker-compose.yml
version: '3.9'

services:
  # Vector Database
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage

  # Relational DB (metadata, users, eval logs)
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: rag_db
      POSTGRES_USER: rag_user
      POSTGRES_PASSWORD: rag_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  # Cache + Queue Broker
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  # LLM Server (pull model separately: ollama pull mistral)
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]   # Remove if no GPU

  # Backend API
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - QDRANT_HOST=qdrant
      - POSTGRES_URL=postgresql://rag_user:rag_password@postgres:5432/rag_db
      - REDIS_URL=redis://redis:6379
      - OLLAMA_URL=http://ollama:11434
    depends_on:
      - qdrant
      - postgres
      - redis
      - ollama

  # Celery Worker
  worker:
    build: ./backend
    command: celery -A app.workers.celery_app worker --loglevel=info
    environment:
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis

  # Frontend
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend

  # Monitoring
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./infra/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3001:3000"
    volumes:
      - grafana_data:/var/lib/grafana

volumes:
  qdrant_data:
  postgres_data:
  redis_data:
  ollama_data:
  grafana_data:
```

### 0.3 Configuration Pattern (Always Use Pydantic Settings)

```python
# backend/app/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # LLM
    OLLAMA_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "mistral"
    LLM_TEMPERATURE: float = 0.1  # Low for RAG — factual, not creative
    
    # Embeddings
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_BATCH_SIZE: int = 32
    
    # Qdrant
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "company_docs"
    
    # Retrieval
    TOP_K_DENSE: int = 20      # Retrieve more, rerank down
    TOP_K_SPARSE: int = 20
    TOP_K_FINAL: int = 5       # Final chunks passed to LLM
    
    # Chunking
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50
    
    # PostgreSQL
    POSTGRES_URL: str = "postgresql://..."
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    CACHE_TTL_SECONDS: int = 3600
    
    # Auth
    SECRET_KEY: str = "change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    class Config:
        env_file = ".env"

settings = Settings()
```

---

## Phase 1 — Data Sourcing & Web Scraping

### 1.1 What Are We Scraping? (Company Context)

For a company assistant, your data sources are:

```
INTERNAL DATA SOURCES (High Priority)
├── Company documentation (PDFs, DOCX)
├── Internal wikis / Notion exports
├── HR policies
├── Product manuals
└── FAQ documents

EXTERNAL DATA SOURCES (Lower Priority)
├── Company website
├── Product documentation pages
├── Support pages
└── Blog posts
```

### 1.2 Architecture Decision — Scraping Approach

**Approach A: Scrapy (for static sites)**
- Use when: HTML pages, pagination, large crawls
- Free, fast, battle-tested
- Best for: documentation sites, FAQs

**Approach B: Playwright (for JS-heavy sites)**
- Use when: React/Vue sites, SPAs, lazy loading
- Slightly slower but handles dynamic content
- Best for: modern web apps

**Approach C: Direct file ingestion**
- Use when: you have the files already (PDFs, DOCX)
- Fastest path to value
- **Start here for a company assistant**

### 1.3 Implementation — Scrapy Spider

```python
# scraping/scrapy_project/spiders/company_spider.py
import scrapy
from scrapy.crawler import CrawlerProcess

class CompanyDocSpider(scrapy.Spider):
    name = "company_docs"
    
    # Config: restrict to your domain
    allowed_domains = ["docs.yourcompany.com"]
    start_urls = ["https://docs.yourcompany.com/"]
    
    custom_settings = {
        "DEPTH_LIMIT": 5,
        "DOWNLOAD_DELAY": 1,       # Respect robots.txt spirit
        "CONCURRENT_REQUESTS": 8,
        "USER_AGENT": "CompanyRAGBot/1.0 (internal use)",
        "FEEDS": {
            "output/scraped_pages.jsonl": {"format": "jsonlines"}
        }
    }
    
    def parse(self, response):
        # Extract page content
        yield {
            "url": response.url,
            "title": response.css("title::text").get(""),
            "h1": response.css("h1::text").get(""),
            "content": " ".join(response.css(
                "p::text, h2::text, h3::text, li::text"
            ).getall()),
            "raw_html": response.text,
            "crawled_at": response.headers.get("Date", b"").decode()
        }
        
        # Follow internal links
        for href in response.css("a::attr(href)").getall():
            yield response.follow(href, self.parse)
```

### 1.4 Implementation — Playwright (JS Sites)

```python
# scraping/playwright_scripts/dynamic_scraper.py
from playwright.async_api import async_playwright
import asyncio, json

async def scrape_page(url: str) -> dict:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await page.goto(url, wait_until="networkidle")
        
        # Wait for content to load
        await page.wait_for_selector("main", timeout=10000)
        
        content = await page.evaluate("""() => {
            // Remove nav, footer, ads
            ['nav', 'footer', 'header', '.sidebar', '.ads'].forEach(sel => {
                document.querySelectorAll(sel).forEach(el => el.remove());
            });
            return {
                title: document.title,
                content: document.body.innerText,
                url: window.location.href
            };
        }""")
        
        await browser.close()
        return content

async def batch_scrape(urls: list[str]) -> list[dict]:
    return await asyncio.gather(*[scrape_page(url) for url in urls])
```

### 1.5 Scraping Output Format (Standardize Early)

```python
# Every scraper outputs this schema — enforced by Pydantic
from pydantic import BaseModel
from datetime import datetime

class RawDocument(BaseModel):
    source_id: str              # Unique hash of URL/filepath
    source_type: str            # "web", "pdf", "docx", "api"
    source_url: str
    title: str
    raw_content: str
    metadata: dict              # Page-specific metadata
    scraped_at: datetime
    content_hash: str           # For deduplication
```

---

## Phase 2 — Data Ingestion Pipeline

### 2.1 Architecture — The Ingestion Flow

```
RAW SOURCE
    │
    ▼
SOURCE DETECTOR      → Detect file type (PDF/DOCX/HTML/TXT)
    │
    ▼
APPROPRIATE PARSER   → Extract clean text + structure
    │
    ▼
TEXT CLEANER         → Remove noise, normalize whitespace
    │
    ▼
METADATA EXTRACTOR   → Title, date, author, section info
    │
    ▼
DEDUPLICATION CHECK  → Skip if content_hash already in DB
    │
    ▼
CHUNKER              → Split into retrieval units (Phase 3)
    │
    ▼
EMBEDDER             → Convert chunks to vectors (Phase 4)
    │
    ▼
VECTOR DB UPSERT     → Store in Qdrant with metadata
    │
    ▼
METADATA DB INSERT   → Log to PostgreSQL for tracking
```

### 2.2 Parser Implementations

#### PDF Parser (PyMuPDF — Best Free Option)

```python
# backend/app/ingestion/parsers/pdf_parser.py
import fitz  # PyMuPDF
from pathlib import Path

class PDFParser:
    """
    Why PyMuPDF over pdfplumber or PyPDF2?
    - Faster (C++ backend)
    - Better text ordering on complex layouts
    - Handles tables reasonably
    - Free
    """
    
    def parse(self, filepath: str) -> dict:
        doc = fitz.open(filepath)
        
        pages = []
        toc = doc.get_toc()  # Table of contents for structure awareness
        
        for page_num, page in enumerate(doc):
            blocks = page.get_text("dict")["blocks"]
            
            page_content = {
                "page_number": page_num + 1,
                "text": "",
                "headings": [],
                "tables": []
            }
            
            for block in blocks:
                if block["type"] == 0:  # Text block
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text = span["text"].strip()
                            font_size = span["size"]
                            
                            # Heuristic: large font = heading
                            if font_size > 14:
                                page_content["headings"].append(text)
                            else:
                                page_content["text"] += text + " "
            
            pages.append(page_content)
        
        return {
            "pages": pages,
            "toc": toc,
            "num_pages": len(doc),
            "full_text": "\n".join(p["text"] for p in pages),
            "headings": [h for p in pages for h in p["headings"]]
        }
```

#### HTML Parser (BeautifulSoup)

```python
# backend/app/ingestion/parsers/html_parser.py
from bs4 import BeautifulSoup
import re

class HTMLParser:
    # Tags that never contain useful content
    NOISE_TAGS = ['script', 'style', 'nav', 'footer', 'header', 
                  'aside', 'advertisement', 'cookie-banner']
    
    def parse(self, html: str, url: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        
        # Remove noise
        for tag in self.NOISE_TAGS:
            for el in soup.find_all(tag):
                el.decompose()
        
        # Extract structure
        headings = {
            f"h{i}": [h.get_text(strip=True) for h in soup.find_all(f"h{i}")]
            for i in range(1, 7)
        }
        
        # Main content heuristic: article > main > div.content > body
        main = (
            soup.find("article") or 
            soup.find("main") or
            soup.find("div", {"class": re.compile("content|article|post")}) or
            soup.find("body")
        )
        
        # Clean text extraction
        text = self._clean_text(main.get_text(separator="\n"))
        
        return {
            "text": text,
            "headings": headings,
            "title": soup.find("title").get_text(strip=True) if soup.find("title") else "",
            "meta_description": self._get_meta(soup, "description"),
            "url": url
        }
    
    def _clean_text(self, text: str) -> str:
        # Remove excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        return text.strip()
    
    def _get_meta(self, soup, name: str) -> str:
        tag = soup.find("meta", {"name": name})
        return tag["content"] if tag and "content" in tag.attrs else ""
```

### 2.3 Text Cleaning Pipeline

```python
# backend/app/ingestion/cleaner.py
import re
from typing import Optional

class TextCleaner:
    """
    Applied after parsing, before chunking.
    Order matters — run these in sequence.
    """
    
    def clean(self, text: str, source_type: str) -> str:
        text = self._remove_control_chars(text)
        text = self._normalize_unicode(text)
        text = self._fix_whitespace(text)
        text = self._remove_boilerplate(text, source_type)
        text = self._fix_hyphenation(text)  # "infor-\nmation" → "information"
        return text
    
    def _remove_control_chars(self, text: str) -> str:
        return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    
    def _normalize_unicode(self, text: str) -> str:
        import unicodedata
        return unicodedata.normalize("NFKC", text)
    
    def _fix_whitespace(self, text: str) -> str:
        text = re.sub(r'[ \t]+', ' ', text)      # Multiple spaces → one
        text = re.sub(r'\n{3,}', '\n\n', text)   # Triple+ newlines → double
        return text.strip()
    
    def _remove_boilerplate(self, text: str, source_type: str) -> str:
        if source_type == "web":
            # Remove common web boilerplate
            patterns = [
                r'Cookie Policy.*?Accept',
                r'Subscribe to our newsletter.*?\n',
                r'Share this article.*?\n',
                r'©\s*\d{4}.*?reserved\.',
            ]
            for pat in patterns:
                text = re.sub(pat, '', text, flags=re.IGNORECASE | re.DOTALL)
        return text
    
    def _fix_hyphenation(self, text: str) -> str:
        # Fix PDF-extracted hyphenated words
        return re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)
```

---

## Phase 3 — Chunking Engine

### 3.1 Why Chunking is the Most Critical Phase

> "Chunking quality IS system quality. A perfect LLM with bad chunks gives wrong answers. A mediocre LLM with great chunks gives good answers."

The goal of chunking:
- Chunks must be **self-contained** (make sense alone)
- Chunks must be **retrieval-sized** (not too large, not too small)
- Chunks must **preserve context** (where did this come from? what section?)

### 3.2 Chunking Strategy Decision Tree

```
Is your document structured (headings, sections)?
│
├── YES → Start with STRUCTURAL chunking
│          Then apply sliding window on long sections
│
└── NO → Is semantic coherence critical?
          │
          ├── YES → SEMANTIC chunking (sentence-transformers)
          │
          └── NO → SLIDING WINDOW (fast baseline)

Are chunks being used for complex multi-hop queries?
│
└── YES → Use HIERARCHICAL chunking on top of any of the above
```

### 3.3 Approach 1 — Sliding Window Chunker

```python
# backend/app/ingestion/chunkers/sliding_window_chunker.py
from dataclasses import dataclass
from typing import List

@dataclass
class Chunk:
    text: str
    chunk_index: int
    start_char: int
    end_char: int
    metadata: dict  # Inherited from parent document

class SlidingWindowChunker:
    """
    Baseline chunker. Use when structure is unknown.
    
    TRADEOFF: 
    - Fast, simple, consistent chunk sizes
    - BUT: may cut mid-sentence or mid-concept
    - MITIGATED BY: overlap (last N chars of prev chunk)
    """
    
    def __init__(self, chunk_size: int = 512, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap
    
    def chunk(self, text: str, base_metadata: dict) -> List[Chunk]:
        # Prefer to split on sentence boundaries
        import nltk
        sentences = nltk.sent_tokenize(text)
        
        chunks = []
        current_chunk = ""
        chunk_idx = 0
        start_char = 0
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= self.chunk_size:
                current_chunk += " " + sentence
            else:
                if current_chunk.strip():
                    chunks.append(Chunk(
                        text=current_chunk.strip(),
                        chunk_index=chunk_idx,
                        start_char=start_char,
                        end_char=start_char + len(current_chunk),
                        metadata={**base_metadata, "chunk_method": "sliding_window"}
                    ))
                    chunk_idx += 1
                    start_char += len(current_chunk) - self.overlap
                    # Overlap: keep last N chars as context bridge
                    current_chunk = current_chunk[-self.overlap:] + " " + sentence
        
        # Don't forget the last chunk
        if current_chunk.strip():
            chunks.append(Chunk(
                text=current_chunk.strip(),
                chunk_index=chunk_idx,
                start_char=start_char,
                end_char=start_char + len(current_chunk),
                metadata={**base_metadata, "chunk_method": "sliding_window"}
            ))
        
        return chunks
```

### 3.4 Approach 2 — Structural Chunker (Best for Docs/PDFs)

```python
# backend/app/ingestion/chunkers/structural_chunker.py
import re
from typing import List
from .sliding_window_chunker import Chunk, SlidingWindowChunker

class StructuralChunker:
    """
    Splits by document headings/sections first.
    Then applies sliding window on long sections.
    
    BEST FOR: Company docs, PDFs, wiki pages, manuals
    WHY: Keeps related content together naturally
    
    TRADEOFF: Requires structured source (heading detection)
    """
    
    HEADING_PATTERNS = [
        r'^#+\s+.+$',           # Markdown headings
        r'^[A-Z][^.!?]*:\s*$',  # Sentence-case headings ending in :
        r'^\d+\.\s+[A-Z].+$',  # Numbered sections
    ]
    
    def __init__(self, max_chunk_size: int = 1000, overlap: int = 50):
        self.max_chunk_size = max_chunk_size
        self.fallback_chunker = SlidingWindowChunker(
            chunk_size=max_chunk_size, 
            overlap=overlap
        )
    
    def chunk(self, text: str, base_metadata: dict) -> List[Chunk]:
        sections = self._split_by_headings(text)
        all_chunks = []
        global_idx = 0
        
        for section in sections:
            heading = section.get("heading", "")
            content = section["content"]
            section_metadata = {
                **base_metadata,
                "section_heading": heading,
                "chunk_method": "structural"
            }
            
            if len(content) <= self.max_chunk_size:
                # Section fits in one chunk
                all_chunks.append(Chunk(
                    text=f"{heading}\n\n{content}".strip() if heading else content,
                    chunk_index=global_idx,
                    start_char=0,
                    end_char=len(content),
                    metadata=section_metadata
                ))
                global_idx += 1
            else:
                # Section is too long — apply sliding window
                sub_chunks = self.fallback_chunker.chunk(content, section_metadata)
                for chunk in sub_chunks:
                    # Prepend heading to maintain context
                    if heading:
                        chunk.text = f"[Section: {heading}]\n{chunk.text}"
                    chunk.chunk_index = global_idx
                    all_chunks.append(chunk)
                    global_idx += 1
        
        return all_chunks
    
    def _split_by_headings(self, text: str) -> list:
        lines = text.split('\n')
        sections = []
        current_heading = ""
        current_content = []
        
        for line in lines:
            if self._is_heading(line):
                if current_content:
                    sections.append({
                        "heading": current_heading,
                        "content": "\n".join(current_content).strip()
                    })
                current_heading = line.strip()
                current_content = []
            else:
                current_content.append(line)
        
        # Last section
        if current_content:
            sections.append({
                "heading": current_heading,
                "content": "\n".join(current_content).strip()
            })
        
        return sections
    
    def _is_heading(self, line: str) -> bool:
        return any(re.match(pat, line.strip()) for pat in self.HEADING_PATTERNS)
```

### 3.5 Approach 3 — Semantic Chunker

```python
# backend/app/ingestion/chunkers/semantic_chunker.py
from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List
from .sliding_window_chunker import Chunk

class SemanticChunker:
    """
    Splits text at semantic breakpoints using cosine similarity.
    Expensive but highest quality for unstructured text.
    
    ALGORITHM:
    1. Split into sentences
    2. Embed each sentence
    3. Find consecutive pairs with LOW similarity (= topic shift)
    4. Split at those boundaries
    5. Merge small chunks
    
    BEST FOR: long-form articles, research docs, transcripts
    TRADEOFF: Slow (embedding every sentence), but pay it once at ingest time
    """
    
    def __init__(
        self, 
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        breakpoint_threshold: float = 0.5,  # Lower = more chunks
        max_chunk_size: int = 800
    ):
        self.model = SentenceTransformer(model_name)
        self.threshold = breakpoint_threshold
        self.max_chunk_size = max_chunk_size
    
    def chunk(self, text: str, base_metadata: dict) -> List[Chunk]:
        import nltk
        sentences = nltk.sent_tokenize(text)
        
        if len(sentences) < 3:
            return [Chunk(
                text=text, chunk_index=0, start_char=0,
                end_char=len(text),
                metadata={**base_metadata, "chunk_method": "semantic"}
            )]
        
        # Embed all sentences at once (batch is faster)
        embeddings = self.model.encode(sentences, batch_size=32, show_progress_bar=False)
        
        # Find breakpoints: where similarity drops
        breakpoints = [0]
        for i in range(1, len(sentences) - 1):
            sim = self._cosine_sim(embeddings[i-1], embeddings[i])
            if sim < self.threshold:
                breakpoints.append(i)
        breakpoints.append(len(sentences))
        
        # Build chunks from breakpoints
        chunks = []
        for i in range(len(breakpoints) - 1):
            start, end = breakpoints[i], breakpoints[i+1]
            chunk_text = " ".join(sentences[start:end])
            
            chunks.append(Chunk(
                text=chunk_text,
                chunk_index=i,
                start_char=0,
                end_char=len(chunk_text),
                metadata={**base_metadata, "chunk_method": "semantic"}
            ))
        
        return chunks
    
    def _cosine_sim(self, a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
```

### 3.6 Approach 4 — Hierarchical Chunker (Advanced RAG)

```python
# backend/app/ingestion/chunkers/hierarchical_chunker.py
"""
HIERARCHICAL CHUNKING — The most sophisticated approach.

CONCEPT:
- Store PARENT chunks (large, ~1000 tokens) for context
- Store CHILD chunks (small, ~128 tokens) for precise retrieval
- At query time: retrieve child chunks, then return their parents

WHY THIS WORKS:
- Small chunks = precise embedding match
- Large chunks = full context for LLM
- Best of both worlds

DATA STRUCTURE:
  parent_chunk_1 (1000 tokens, stored in DB)
  ├── child_chunk_1a (128 tokens, embedded + indexed)
  ├── child_chunk_1b (128 tokens, embedded + indexed)  
  └── child_chunk_1c (128 tokens, embedded + indexed)

RETRIEVAL FLOW:
  Query → match child_chunk_1b → fetch parent_chunk_1 → send to LLM
"""

from dataclasses import dataclass
from typing import List, Optional

@dataclass
class HierarchicalChunk:
    text: str
    chunk_type: str          # "parent" or "child"
    parent_id: Optional[str]
    chunk_id: str
    metadata: dict

class HierarchicalChunker:
    
    def __init__(
        self,
        parent_chunk_size: int = 1000,
        child_chunk_size: int = 128,
        overlap: int = 20
    ):
        self.parent_size = parent_chunk_size
        self.child_size = child_chunk_size
        self.overlap = overlap
    
    def chunk(self, text: str, doc_id: str, base_metadata: dict) -> List[HierarchicalChunk]:
        from .sliding_window_chunker import SlidingWindowChunker
        import uuid
        
        parent_chunker = SlidingWindowChunker(self.parent_size, self.overlap)
        child_chunker = SlidingWindowChunker(self.child_size, self.overlap // 2)
        
        all_chunks = []
        parent_raw = parent_chunker.chunk(text, base_metadata)
        
        for parent_raw_chunk in parent_raw:
            parent_id = str(uuid.uuid4())
            
            # Store parent chunk
            all_chunks.append(HierarchicalChunk(
                text=parent_raw_chunk.text,
                chunk_type="parent",
                parent_id=None,
                chunk_id=parent_id,
                metadata={**base_metadata, "doc_id": doc_id}
            ))
            
            # Create and store child chunks
            child_raw = child_chunker.chunk(parent_raw_chunk.text, base_metadata)
            for child_raw_chunk in child_raw:
                all_chunks.append(HierarchicalChunk(
                    text=child_raw_chunk.text,
                    chunk_type="child",
                    parent_id=parent_id,
                    chunk_id=str(uuid.uuid4()),
                    metadata={**base_metadata, "doc_id": doc_id, "parent_id": parent_id}
                ))
        
        return all_chunks
```

### 3.7 Recommended Final Chunking Strategy

```
FOR THIS PROJECT — Use This Combination:

Step 1: Run STRUCTURAL chunker first
  → This respects document organization
  
Step 2: On long sections, fall back to SLIDING WINDOW with sentence boundaries
  → This prevents huge chunks
  
Step 3: For ingestion of unstructured text (scraped web), use SEMANTIC chunker
  → This produces the best quality at moderate cost

Step 4: On critical documents (policies, manuals), add HIERARCHICAL on top
  → Enables precise retrieval + full context

CHUNK SIZE GUIDELINES:
  - Too small (<100 tokens): loses context, vector doesn't capture meaning
  - Sweet spot (256-512 tokens): balanced
  - Too large (>1000 tokens): LLM context waste, imprecise retrieval
  - Use 512 as your default, tune after eval
```

---

## Phase 4 — Embeddings

### 4.1 Model Selection (Free Options Ranked)

| Model | Dims | Speed | Quality | Best For |
|-------|------|-------|---------|----------|
| `BAAI/bge-m3` | 1024 | Medium | ⭐⭐⭐⭐⭐ | **Use this. Best free multilingual model** |
| `BAAI/bge-large-en-v1.5` | 1024 | Medium | ⭐⭐⭐⭐⭐ | English-only, excellent |
| `all-MiniLM-L6-v2` | 384 | Fast | ⭐⭐⭐ | Good baseline, much faster |
| `all-mpnet-base-v2` | 768 | Medium | ⭐⭐⭐⭐ | Balanced |

**Decision**: Use `BAAI/bge-m3` for quality. Fall back to `all-MiniLM-L6-v2` on low-RAM machines.

### 4.2 Embedder Implementation

```python
# backend/app/ingestion/embedder.py
from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List
import hashlib

class Embedder:
    """
    Centralized embedding service.
    Always batch — never embed one at a time.
    
    BGE models need a special query prefix for better retrieval:
    - At INGEST time: no prefix (embed document text as-is)
    - At QUERY time: prefix with "Represent this sentence for searching relevant passages: "
    """
    
    def __init__(self, model_name: str = "BAAI/bge-m3"):
        self.model = SentenceTransformer(model_name)
        self.model_name = model_name
        self.dimension = self.model.get_sentence_embedding_dimension()
    
    def embed_documents(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """For ingestion — no prefix"""
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
            normalize_embeddings=True  # IMPORTANT: normalize for cosine similarity
        )
        return embeddings.tolist()
    
    def embed_query(self, query: str) -> List[float]:
        """For retrieval — BGE needs query prefix"""
        if "bge" in self.model_name.lower():
            query = f"Represent this sentence for searching relevant passages: {query}"
        
        embedding = self.model.encode(
            [query],
            normalize_embeddings=True
        )
        return embedding[0].tolist()
    
    def get_cache_key(self, text: str) -> str:
        """For Redis cache — hash text to avoid storing full strings"""
        return f"emb:{hashlib.md5(text.encode()).hexdigest()}"
```

---

## Phase 5 — Vector Database

### 5.1 Qdrant Setup and Collection Design

```python
# backend/app/storage/vector_store.py
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, 
    PointStruct, Filter, FieldCondition, MatchValue,
    HnswConfigDiff, OptimizersConfigDiff
)
from typing import List, Optional
import uuid

class VectorStore:
    
    def __init__(self, host: str = "localhost", port: int = 6333):
        self.client = QdrantClient(host=host, port=port)
        self.collection_name = "company_docs"
    
    def create_collection(self, vector_dim: int = 1024):
        """
        Create collection with optimized HNSW settings.
        
        HNSW (Hierarchical Navigable Small World):
        - m: number of bi-directional links (higher = better quality, more memory)
        - ef_construct: size of dynamic candidate list during indexing
        - ef: size during search (higher = more accurate, slower)
        
        For production: m=16, ef_construct=200 is a good balance
        """
        self.client.recreate_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=vector_dim,
                distance=Distance.COSINE,  # BGE models: use COSINE
                hnsw_config=HnswConfigDiff(
                    m=16,
                    ef_construct=200,
                    full_scan_threshold=10000
                )
            ),
            optimizers_config=OptimizersConfigDiff(
                indexing_threshold=20000,  # Start indexing after 20k vectors
                memmap_threshold=50000
            )
        )
        
        # Create payload indexes for fast filtering
        self.client.create_payload_index(
            collection_name=self.collection_name,
            field_name="source_type",
            field_schema="keyword"
        )
        self.client.create_payload_index(
            collection_name=self.collection_name,
            field_name="department",
            field_schema="keyword"
        )
        self.client.create_payload_index(
            collection_name=self.collection_name,
            field_name="doc_date",
            field_schema="float"
        )
    
    def upsert_chunks(self, chunks: list, embeddings: List[List[float]]):
        """Batch upsert for efficiency"""
        points = []
        for chunk, embedding in zip(chunks, embeddings):
            points.append(PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "text": chunk.text,
                    "source_url": chunk.metadata.get("source_url", ""),
                    "source_type": chunk.metadata.get("source_type", ""),
                    "title": chunk.metadata.get("title", ""),
                    "section_heading": chunk.metadata.get("section_heading", ""),
                    "chunk_index": chunk.chunk_index,
                    "chunk_method": chunk.metadata.get("chunk_method", ""),
                    "department": chunk.metadata.get("department", "general"),
                    "doc_date": chunk.metadata.get("doc_date", 0.0),
                    "parent_id": chunk.metadata.get("parent_id", None)
                }
            ))
        
        # Qdrant handles batching internally, but batch manually for large sets
        batch_size = 100
        for i in range(0, len(points), batch_size):
            self.client.upsert(
                collection_name=self.collection_name,
                points=points[i:i+batch_size]
            )
    
    def search(
        self, 
        query_vector: List[float],
        top_k: int = 20,
        filters: Optional[dict] = None
    ) -> list:
        """Dense vector search with optional metadata filtering"""
        
        qdrant_filter = None
        if filters:
            conditions = []
            for key, value in filters.items():
                conditions.append(FieldCondition(
                    key=key,
                    match=MatchValue(value=value)
                ))
            qdrant_filter = Filter(must=conditions)
        
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=top_k,
            query_filter=qdrant_filter,
            with_payload=True,
            score_threshold=0.3  # Filter very low-relevance results
        )
        
        return [
            {
                "id": r.id,
                "text": r.payload["text"],
                "score": r.score,
                "metadata": {k: v for k, v in r.payload.items() if k != "text"}
            }
            for r in results
        ]
    
    def fetch_parent(self, parent_id: str) -> Optional[dict]:
        """For hierarchical chunking — fetch parent chunk by ID"""
        results = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=Filter(
                must=[FieldCondition(key="id", match=MatchValue(value=parent_id))]
            ),
            limit=1,
            with_payload=True
        )
        if results[0]:
            return results[0][0].payload
        return None
```

---

## Phase 6 — Retrieval Engine

### 6.1 Architecture: Hybrid Retrieval (The Right Approach)

```
PURE DENSE (vector only)    — Misses exact keyword matches
PURE SPARSE (BM25 only)     — Misses semantic/paraphrase matches
HYBRID (dense + sparse)     — Best of both worlds ✅

FLOW:
Query 
  ├─→ Dense search (Qdrant)   → Top 20 results
  └─→ BM25 search (rank_bm25) → Top 20 results
          ↓
    Reciprocal Rank Fusion (RRF)
          ↓
    Merged & deduplicated Top 20
          ↓
    Reranker (Phase 7) → Top 5
```

### 6.2 BM25 Index

```python
# backend/app/rag/bm25_index.py
from rank_bm25 import BM25Okapi
import pickle, os
from typing import List

class BM25Index:
    """
    BM25 is a classic keyword search algorithm.
    We maintain a BM25 index in parallel with Qdrant for hybrid search.
    
    PERSISTENCE: Save to disk, rebuild on new ingestion.
    For large scale: use Elasticsearch with BM25 built-in.
    """
    
    def __init__(self, index_path: str = "data/bm25_index.pkl"):
        self.index_path = index_path
        self.index = None
        self.doc_store = []  # Store (chunk_id, text, metadata) tuples
    
    def build(self, chunks: list):
        """Build or rebuild the BM25 index"""
        self.doc_store = [(c.chunk_id, c.text, c.metadata) for c in chunks]
        
        tokenized = [self._tokenize(c.text) for c in chunks]
        self.index = BM25Okapi(tokenized)
        
        self._save()
    
    def search(self, query: str, top_k: int = 20) -> List[dict]:
        if not self.index:
            self._load()
        
        query_tokens = self._tokenize(query)
        scores = self.index.get_scores(query_tokens)
        
        top_indices = scores.argsort()[-top_k:][::-1]
        
        return [
            {
                "id": self.doc_store[i][0],
                "text": self.doc_store[i][1],
                "score": float(scores[i]),
                "metadata": self.doc_store[i][2],
                "retrieval_method": "bm25"
            }
            for i in top_indices
            if scores[i] > 0  # Skip zero-score results
        ]
    
    def _tokenize(self, text: str) -> List[str]:
        import re
        text = text.lower()
        tokens = re.findall(r'\b[a-z]{2,}\b', text)
        # Simple stopword removal
        stopwords = {'the', 'a', 'an', 'is', 'in', 'of', 'to', 'and', 'or'}
        return [t for t in tokens if t not in stopwords]
    
    def _save(self):
        with open(self.index_path, 'wb') as f:
            pickle.dump({'index': self.index, 'doc_store': self.doc_store}, f)
    
    def _load(self):
        with open(self.index_path, 'rb') as f:
            data = pickle.load(f)
            self.index = data['index']
            self.doc_store = data['doc_store']
```

### 6.3 Reciprocal Rank Fusion (RRF)

```python
# backend/app/rag/retriever.py
from typing import List, Dict

class HybridRetriever:
    """
    Combines dense (vector) and sparse (BM25) retrieval using RRF.
    
    RRF FORMULA: score(d) = Σ 1/(k + rank(d))
    where k=60 is a constant that reduces impact of high-rank outliers.
    
    WHY RRF over weighted combination?
    - No need to normalize scores across different methods
    - More robust to outlier scores
    - Proven in academic literature to outperform simple fusion
    """
    
    def __init__(self, vector_store, bm25_index, embedder):
        self.vector_store = vector_store
        self.bm25 = bm25_index
        self.embedder = embedder
        self.k = 60  # RRF constant
    
    def retrieve(
        self, 
        query: str, 
        top_k: int = 20,
        filters: dict = None
    ) -> List[Dict]:
        
        # 1. Dense retrieval
        query_vector = self.embedder.embed_query(query)
        dense_results = self.vector_store.search(
            query_vector, top_k=top_k, filters=filters
        )
        
        # 2. Sparse (BM25) retrieval
        sparse_results = self.bm25.search(query, top_k=top_k)
        
        # 3. Reciprocal Rank Fusion
        fused = self._rrf_merge(dense_results, sparse_results)
        
        return fused[:top_k]
    
    def _rrf_merge(
        self, 
        dense: List[Dict], 
        sparse: List[Dict]
    ) -> List[Dict]:
        
        rrf_scores = {}
        all_docs = {}
        
        # Score dense results
        for rank, doc in enumerate(dense):
            doc_id = doc["id"]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (self.k + rank + 1)
            all_docs[doc_id] = {**doc, "retrieval_methods": ["dense"]}
        
        # Score sparse results
        for rank, doc in enumerate(sparse):
            doc_id = doc["id"]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (self.k + rank + 1)
            if doc_id in all_docs:
                all_docs[doc_id]["retrieval_methods"].append("sparse")
                all_docs[doc_id]["retrieval_methods"] = list(set(
                    all_docs[doc_id]["retrieval_methods"]
                ))
            else:
                all_docs[doc_id] = {**doc, "retrieval_methods": ["sparse"]}
        
        # Sort by RRF score
        sorted_ids = sorted(rrf_scores, key=rrf_scores.get, reverse=True)
        
        result = []
        for doc_id in sorted_ids:
            doc = all_docs[doc_id]
            doc["rrf_score"] = rrf_scores[doc_id]
            result.append(doc)
        
        return result
```

### 6.4 Multi-Query Retrieval (Optional Enhancement)

```python
# backend/app/rag/multi_query_retriever.py
"""
MULTI-QUERY RETRIEVAL:
Generate N variants of the user's query, retrieve for each, then merge.

WHY: Single queries often miss relevant docs due to vocabulary mismatch.
"What is our refund policy?" might miss docs that say "return procedure".

HOW:
  User query → LLM generates 3 variants → retrieve for each → union → rerank
"""

class MultiQueryRetriever:
    
    def __init__(self, base_retriever, llm_client):
        self.retriever = base_retriever
        self.llm = llm_client
    
    async def retrieve(self, query: str, top_k: int = 20) -> list:
        # Generate query variants
        variants = await self._expand_query(query)
        
        # Retrieve for each variant
        all_results = {}
        for variant in [query] + variants:
            results = self.retriever.retrieve(variant, top_k=top_k // 2)
            for r in results:
                if r["id"] not in all_results:
                    all_results[r["id"]] = r
        
        # Return unique results, sorted by RRF score
        return sorted(all_results.values(), key=lambda x: x.get("rrf_score", 0), reverse=True)[:top_k]
    
    async def _expand_query(self, query: str) -> list:
        prompt = f"""Generate 3 alternative search queries for this question.
Return ONLY a JSON array of strings. No explanation.

Original: "{query}"

Generate queries that:
1. Use different vocabulary
2. Are more specific
3. Address related sub-questions"""
        
        response = await self.llm.complete(prompt)
        import json
        try:
            return json.loads(response)[:3]
        except:
            return []  # Fallback to original query only
```

---

## Phase 7 — Reranking

### 7.1 Why Reranking is Essential

```
WITHOUT RERANKING:
  Query: "What is the vacation policy?"
  Retrieved #1: "Our company has 15 vacation days per year." ← CORRECT
  Retrieved #2: "Employees can request time off through HR portal."
  Retrieved #3: "Benefits package overview page 3 of 12" ← NOISE

WITH RERANKING:
  Cross-encoder examines query + each candidate together
  → Better judgment of actual relevance
  → Noise gets pushed down
```

### 7.2 Cross-Encoder Reranker

```python
# backend/app/rag/reranker.py
from sentence_transformers import CrossEncoder
from typing import List, Dict

class Reranker:
    """
    Cross-encoder takes (query, passage) pairs and scores them jointly.
    Much more accurate than bi-encoder (embedding similarity) alone.
    
    FLOW: Top 20 candidates → cross-encoder scores → Top 5
    
    MODEL: cross-encoder/ms-marco-MiniLM-L-6-v2
    - Fast, lightweight
    - Trained on MS-MARCO (real search queries)
    - Free
    
    TRADEOFF: 
    - Slower than bi-encoder (scales O(n) not O(1))
    - But we only rerank ~20 docs, so it's fast enough
    """
    
    def __init__(
        self, 
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        top_k: int = 5
    ):
        self.model = CrossEncoder(model_name, max_length=512)
        self.top_k = top_k
    
    def rerank(self, query: str, candidates: List[Dict]) -> List[Dict]:
        if not candidates:
            return []
        
        # Create (query, passage) pairs
        pairs = [(query, doc["text"]) for doc in candidates]
        
        # Score all pairs
        scores = self.model.predict(pairs, show_progress_bar=False)
        
        # Attach scores and sort
        for doc, score in zip(candidates, scores):
            doc["rerank_score"] = float(score)
        
        reranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
        
        return reranked[:self.top_k]
```

---

## Phase 8 — Query Intelligence Layer

### 8.1 Query Processing Pipeline

```
Raw User Query
    │
    ▼
INTENT DETECTOR          → classify: factual / procedural / comparison / chitchat
    │
    ▼
QUERY CLASSIFIER         → route to appropriate retrieval strategy
    │
    ▼
QUERY REWRITER           → fix typos, expand abbreviations, clarify pronouns
    │
    ▼
QUERY EXPANDER           → add synonyms / related terms
    │
    ▼
FILTER EXTRACTOR         → detect department/date filters in query
    │
    ▼
PROCESSED QUERY → Retrieval Engine
```

### 8.2 Implementation

```python
# backend/app/rag/query_processor.py
import re
from typing import Optional
from dataclasses import dataclass

@dataclass
class ProcessedQuery:
    original: str
    rewritten: str
    intent: str              # "factual", "procedural", "comparison", "chitchat"
    filters: dict            # {"department": "HR", "doc_type": "policy"}
    expanded_terms: list
    should_use_multi_query: bool

class QueryProcessor:
    
    INTENT_PATTERNS = {
        "procedural": [r"how (do|can|to)", r"steps to", r"process for", r"procedure"],
        "factual": [r"what is", r"when (is|was|did)", r"who is", r"where is"],
        "comparison": [r"vs", r"difference between", r"compare", r"better"],
        "chitchat": [r"hello|hi|hey", r"thanks|thank you", r"how are you"]
    }
    
    DEPARTMENT_KEYWORDS = {
        "HR": ["leave", "vacation", "salary", "payroll", "benefits", "employee"],
        "IT": ["software", "laptop", "password", "VPN", "email", "account"],
        "Finance": ["budget", "expense", "reimbursement", "invoice", "payment"],
        "Legal": ["contract", "compliance", "policy", "NDA", "agreement"]
    }
    
    def process(self, query: str) -> ProcessedQuery:
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
            should_use_multi_query=(intent in ["factual", "procedural"] and len(query.split()) > 5)
        )
    
    def _detect_intent(self, query: str) -> str:
        query_lower = query.lower()
        for intent, patterns in self.INTENT_PATTERNS.items():
            if any(re.search(p, query_lower) for p in patterns):
                return intent
        return "factual"  # Default
    
    def _extract_filters(self, query: str) -> dict:
        filters = {}
        query_lower = query.lower()
        for dept, keywords in self.DEPARTMENT_KEYWORDS.items():
            if any(kw in query_lower for kw in keywords):
                filters["department"] = dept
                break
        return filters
    
    def _rewrite(self, query: str) -> str:
        # Expand common abbreviations
        replacements = {
            "PTO": "paid time off",
            "OOO": "out of office",
            "WFH": "work from home",
            "EOD": "end of day",
        }
        for abbr, expansion in replacements.items():
            query = re.sub(rf'\b{abbr}\b', expansion, query, flags=re.IGNORECASE)
        return query
    
    def _expand_terms(self, query: str) -> list:
        # Simple synonym expansion (extend this with a thesaurus or LLM)
        synonyms = {
            "policy": ["rule", "guideline", "procedure"],
            "employee": ["staff", "worker", "team member"],
            "request": ["apply", "submit", "ask"],
        }
        terms = []
        for word in query.lower().split():
            if word in synonyms:
                terms.extend(synonyms[word])
        return terms
```

---

## Phase 9 — LLM & Context Engineering

### 9.1 LLM Client (Ollama)

```python
# backend/app/rag/llm_client.py
import httpx
from typing import AsyncGenerator

class OllamaClient:
    """
    Ollama runs LLMs locally. Free, private, no rate limits.
    
    Models (choose by hardware):
    - 8GB RAM:  mistral:7b or llama3.1:8b
    - 16GB RAM: mixtral:8x7b (better reasoning)  
    - 32GB+ RAM: llama3.1:70b (near GPT-4 quality)
    """
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "mistral"):
        self.base_url = base_url
        self.model = model
    
    async def generate(
        self, 
        prompt: str, 
        system_prompt: str = "",
        temperature: float = 0.1
    ) -> str:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "system": system_prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "top_p": 0.9,
                        "num_ctx": 4096
                    }
                }
            )
            return response.json()["response"]
    
    async def stream_generate(
        self,
        prompt: str,
        system_prompt: str = ""
    ) -> AsyncGenerator[str, None]:
        """For streaming responses to frontend"""
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "system": system_prompt,
                    "stream": True,
                    "options": {"temperature": 0.1}
                }
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        import json
                        data = json.loads(line)
                        if not data.get("done"):
                            yield data.get("response", "")
```

### 9.2 Context Builder

```python
# backend/app/rag/context_builder.py
from typing import List, Dict

class ContextBuilder:
    """
    Assembles retrieved chunks into a coherent context for the LLM.
    
    KEY RULES:
    1. Remove redundant chunks (deduplicate by content similarity)
    2. Order by relevance (highest score first)
    3. Include source citations in context
    4. Stay within token budget
    5. Add clear section separators
    """
    
    MAX_CONTEXT_TOKENS = 3000  # Leave room for prompt + answer
    AVG_CHARS_PER_TOKEN = 4
    MAX_CONTEXT_CHARS = MAX_CONTEXT_TOKENS * AVG_CHARS_PER_TOKEN
    
    def build(self, chunks: List[Dict], query: str) -> tuple[str, List[Dict]]:
        """
        Returns: (formatted_context_string, list_of_sources)
        """
        
        # Deduplicate
        chunks = self._deduplicate(chunks)
        
        # Build context with token budget
        context_parts = []
        sources = []
        char_count = 0
        
        for i, chunk in enumerate(chunks, 1):
            chunk_text = chunk["text"]
            source_label = f"[Source {i}]"
            formatted = f"{source_label}\n{chunk_text}\n"
            
            if char_count + len(formatted) > self.MAX_CONTEXT_CHARS:
                break  # Budget exceeded
            
            context_parts.append(formatted)
            char_count += len(formatted)
            sources.append({
                "index": i,
                "title": chunk["metadata"].get("title", "Unknown"),
                "url": chunk["metadata"].get("source_url", ""),
                "section": chunk["metadata"].get("section_heading", ""),
                "score": chunk.get("rerank_score", chunk.get("rrf_score", 0))
            })
        
        context = "\n---\n".join(context_parts)
        return context, sources
    
    def _deduplicate(self, chunks: List[Dict]) -> List[Dict]:
        """Remove chunks with >80% text overlap"""
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
```

### 9.3 The RAG System Prompt (Critical)

```python
# backend/app/rag/prompts.py

RAG_SYSTEM_PROMPT = """You are a knowledgeable and precise company assistant. Your role is to answer employee questions using ONLY the information provided in the context below.

STRICT RULES:
1. ONLY use information from the provided context
2. If the context does not contain sufficient information, say: "I don't have enough information in my knowledge base to answer this. Please contact [relevant team]."
3. NEVER make up information or use general knowledge to fill gaps
4. ALWAYS cite your sources using [Source N] notation
5. If multiple sources say different things, acknowledge the discrepancy
6. Be concise and direct — employees need fast, actionable answers
7. For policies and procedures, quote the exact wording when possible

RESPONSE FORMAT:
- Start with a direct answer
- Support with evidence from sources
- End with relevant source citations
- If action is needed, list clear steps

TONE: Professional, helpful, factual. Never speculative."""

RAG_QUERY_TEMPLATE = """CONTEXT:
{context}

---

EMPLOYEE QUESTION: {query}

Based on the above context, provide a precise, grounded answer:"""

FALLBACK_RESPONSE = """I couldn't find relevant information in our knowledge base to answer your question accurately.

Please try:
1. Rephrasing your question with different keywords
2. Contacting HR directly for policy questions
3. Reaching out to IT support for technical issues
4. Checking the company intranet for the latest documents

Is there anything else I can help you with?"""
```

---

## Phase 10 — RAG Core Orchestration

### 10.1 The Full RAG Pipeline (Wiring It All Together)

```python
# backend/app/rag/pipeline.py
from typing import AsyncGenerator
import time
import logging

logger = logging.getLogger(__name__)

class RAGPipeline:
    """
    The orchestrator. Wires together all phases.
    
    QUERY FLOW:
    Input → QueryProcessor → MultiQueryRetriever → Reranker → ContextBuilder → LLM → Output
    """
    
    def __init__(
        self,
        query_processor,
        retriever,
        reranker,
        context_builder,
        llm_client,
        cache,
        eval_logger
    ):
        self.query_processor = query_processor
        self.retriever = retriever
        self.reranker = reranker
        self.context_builder = context_builder
        self.llm = llm_client
        self.cache = cache
        self.eval_logger = eval_logger
    
    async def query(self, user_query: str, user_id: str) -> dict:
        start_time = time.time()
        
        # 0. Check response cache
        cached = await self.cache.get_response(user_query)
        if cached:
            return {**cached, "from_cache": True}
        
        # 1. Process query
        processed = self.query_processor.process(user_query)
        
        # Bail early for chitchat
        if processed.intent == "chitchat":
            return {
                "answer": "Hello! I'm your company assistant. How can I help you today?",
                "sources": [],
                "intent": "chitchat"
            }
        
        # 2. Retrieve
        candidates = await self.retriever.retrieve(
            query=processed.rewritten,
            top_k=20,
            filters=processed.filters
        )
        
        if not candidates:
            return {
                "answer": FALLBACK_RESPONSE,
                "sources": [],
                "intent": processed.intent
            }
        
        # 3. Rerank
        reranked = self.reranker.rerank(
            query=processed.rewritten,
            candidates=candidates
        )
        
        # 4. Build context
        context, sources = self.context_builder.build(reranked, user_query)
        
        # 5. Generate answer
        from .prompts import RAG_SYSTEM_PROMPT, RAG_QUERY_TEMPLATE
        
        prompt = RAG_QUERY_TEMPLATE.format(
            context=context,
            query=user_query
        )
        
        answer = await self.llm.generate(
            prompt=prompt,
            system_prompt=RAG_SYSTEM_PROMPT,
            temperature=0.1
        )
        
        result = {
            "answer": answer,
            "sources": sources,
            "intent": processed.intent,
            "query_rewritten": processed.rewritten,
            "chunks_retrieved": len(candidates),
            "chunks_after_rerank": len(reranked),
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        
        # 6. Cache response
        await self.cache.set_response(user_query, result)
        
        # 7. Log for evaluation
        await self.eval_logger.log(
            query=user_query,
            processed_query=processed,
            retrieved_chunks=candidates,
            final_chunks=reranked,
            answer=answer,
            sources=sources,
            latency_ms=result["latency_ms"],
            user_id=user_id
        )
        
        return result
    
    async def stream_query(self, user_query: str, user_id: str) -> AsyncGenerator:
        """Streaming version for real-time frontend"""
        
        processed = self.query_processor.process(user_query)
        candidates = await self.retriever.retrieve(processed.rewritten, top_k=20)
        reranked = self.reranker.rerank(processed.rewritten, candidates)
        context, sources = self.context_builder.build(reranked, user_query)
        
        from .prompts import RAG_SYSTEM_PROMPT, RAG_QUERY_TEMPLATE
        prompt = RAG_QUERY_TEMPLATE.format(context=context, query=user_query)
        
        # Yield sources first (for UI to show while text streams)
        yield {"type": "sources", "data": sources}
        
        # Stream the answer
        async for token in self.llm.stream_generate(prompt, RAG_SYSTEM_PROMPT):
            yield {"type": "token", "data": token}
        
        yield {"type": "done", "data": None}
```

---

## Phase 11 — Backend API

### 11.1 FastAPI Application

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.routes import query, ingest, admin, auth
from app.core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize all connections
    print("🚀 Starting RAG Company Assistant...")
    # TODO: initialize DB connections, load models
    yield
    # Shutdown: cleanup
    print("🛑 Shutting down...")

app = FastAPI(
    title="Company RAG Assistant API",
    version="1.0.0",
    docs_url="/api/docs",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(query.router, prefix="/api/query", tags=["query"])
app.include_router(ingest.router, prefix="/api/ingest", tags=["ingest"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "1.0.0"}
```

### 11.2 Query Endpoint with Streaming

```python
# backend/app/api/routes/query.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json

router = APIRouter()

class QueryRequest(BaseModel):
    query: str
    stream: bool = False
    filters: dict = {}

class QueryResponse(BaseModel):
    answer: str
    sources: list
    intent: str
    latency_ms: int
    from_cache: bool = False

@router.post("/", response_model=QueryResponse)
async def query_endpoint(
    request: QueryRequest,
    current_user = Depends(get_current_user),
    pipeline = Depends(get_pipeline)
):
    if len(request.query.strip()) < 3:
        raise HTTPException(400, "Query too short")
    
    if request.stream:
        async def event_stream():
            async for event in pipeline.stream_query(request.query, current_user.id):
                yield f"data: {json.dumps(event)}\n\n"
        
        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        )
    
    result = await pipeline.query(request.query, current_user.id)
    return QueryResponse(**result)

@router.post("/feedback")
async def submit_feedback(
    query_id: str,
    rating: int,  # 1-5
    comment: str = "",
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    """Collect user feedback for evaluation"""
    await db.log_feedback(query_id, current_user.id, rating, comment)
    return {"status": "feedback recorded"}
```

### 11.3 Ingest Endpoint

```python
# backend/app/api/routes/ingest.py
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, Depends
from typing import List

router = APIRouter()

@router.post("/upload")
async def upload_documents(
    files: List[UploadFile] = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user = Depends(get_admin_user)
):
    """
    Upload files for ingestion.
    Processing happens in background (Celery task).
    """
    task_ids = []
    
    for file in files:
        # Save temporarily
        temp_path = f"/tmp/{file.filename}"
        with open(temp_path, "wb") as f:
            f.write(await file.read())
        
        # Queue background task
        from app.workers.tasks import process_document
        task = process_document.delay(temp_path, file.content_type)
        task_ids.append(task.id)
    
    return {
        "message": f"Queued {len(files)} files for processing",
        "task_ids": task_ids
    }

@router.get("/status/{task_id}")
async def ingest_status(task_id: str):
    from app.workers.celery_app import celery_app
    task = celery_app.AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": task.status,
        "result": task.result if task.ready() else None
    }
```

---

## Phase 12 — Frontend

### 12.1 Architecture Decision: Next.js 14 (App Router)

**Why Next.js:**
- Server-Side Streaming support (for LLM streaming)
- `useChat`-like hooks easy to implement
- TypeScript native
- Free to host on Vercel (free tier)

### 12.2 Chat Interface Component

```typescript
// frontend/app/page.tsx
"use client";
import { useState, useRef, useEffect } from "react";
import MessageBubble from "@/components/MessageBubble";
import SourceCitation from "@/components/SourceCitation";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  latency_ms?: number;
}

interface Source {
  index: number;
  title: string;
  url: string;
  section: string;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    // Add placeholder for streaming response
    const assistantId = (Date.now() + 1).toString();
    setMessages((prev) => [
      ...prev,
      { id: assistantId, role: "assistant", content: "", sources: [] },
    ]);

    try {
      const response = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: input, stream: true }),
      });

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let fullContent = "";
      let sources: Source[] = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split("\n").filter((l) => l.startsWith("data: "));

        for (const line of lines) {
          const event = JSON.parse(line.replace("data: ", ""));

          if (event.type === "sources") {
            sources = event.data;
          } else if (event.type === "token") {
            fullContent += event.data;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, content: fullContent, sources }
                  : m
              )
            );
          }
        }
      }
    } catch (error) {
      console.error("Query failed:", error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b px-6 py-4 shadow-sm">
        <h1 className="text-xl font-semibold text-gray-800">
          🏢 Company Assistant
        </h1>
        <p className="text-sm text-gray-500">Powered by your company knowledge base</p>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-400 mt-20">
            <p className="text-2xl mb-2">👋</p>
            <p>Ask me anything about company policies, procedures, or information.</p>
          </div>
        )}
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {isLoading && messages[messages.length - 1]?.content === "" && (
          <div className="flex items-center gap-2 text-gray-400">
            <div className="animate-bounce">●</div>
            <div className="animate-bounce delay-100">●</div>
            <div className="animate-bounce delay-200">●</div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="bg-white border-t px-4 py-4">
        <div className="flex gap-3 max-w-4xl mx-auto">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendMessage()}
            placeholder="Ask about HR policies, IT support, company procedures..."
            className="flex-1 border rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={sendMessage}
            disabled={isLoading}
            className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {isLoading ? "Thinking..." : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}
```

### 12.3 Message Bubble with Source Citations

```typescript
// frontend/components/MessageBubble.tsx
import SourceCitation from "./SourceCitation";

interface Props {
  message: {
    role: "user" | "assistant";
    content: string;
    sources?: any[];
  };
}

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} max-w-4xl mx-auto w-full`}>
      <div className={`max-w-2xl rounded-2xl px-4 py-3 ${
        isUser 
          ? "bg-blue-600 text-white" 
          : "bg-white border shadow-sm text-gray-800"
      }`}>
        {/* Render markdown-like content */}
        <div className="whitespace-pre-wrap text-sm leading-relaxed">
          {message.content || (
            <span className="italic text-gray-400">Thinking...</span>
          )}
        </div>
        
        {/* Sources */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-100">
            <p className="text-xs text-gray-400 mb-2 font-medium">Sources</p>
            <div className="space-y-1">
              {message.sources.map((source) => (
                <SourceCitation key={source.index} source={source} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
```

---

## Phase 13 — Async Pipeline & Queue

### 13.1 Celery Tasks for Background Ingestion

```python
# backend/app/workers/tasks.py
from app.workers.celery_app import celery_app
from app.ingestion.pipeline import IngestionPipeline

@celery_app.task(bind=True, max_retries=3)
def process_document(self, filepath: str, content_type: str):
    """
    Async document ingestion task.
    Retries 3 times on failure with exponential backoff.
    """
    try:
        pipeline = IngestionPipeline()
        result = pipeline.ingest_file(filepath, content_type)
        return {
            "status": "success",
            "chunks_created": result["num_chunks"],
            "doc_id": result["doc_id"]
        }
    except Exception as exc:
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)

@celery_app.task
def process_url(url: str, source_type: str = "web"):
    """Crawl and ingest a URL"""
    from app.ingestion.scrapers.playwright_scraper import scrape_page
    import asyncio
    
    raw = asyncio.run(scrape_page(url))
    pipeline = IngestionPipeline()
    return pipeline.ingest_raw(raw, source_type="web")

@celery_app.task
def rebuild_bm25_index():
    """Rebuild BM25 index after bulk ingestion"""
    from app.rag.bm25_index import BM25Index
    from app.storage.vector_store import VectorStore
    
    # Fetch all docs from Qdrant and rebuild
    vs = VectorStore()
    all_docs = vs.fetch_all()
    
    bm25 = BM25Index()
    bm25.build(all_docs)
    
    return {"status": "BM25 index rebuilt", "num_docs": len(all_docs)}
```

---

## Phase 14 — Caching Layer

### 14.1 Two-Level Cache Strategy

```python
# backend/app/storage/cache.py
import redis.asyncio as redis
import json, hashlib
from typing import Optional

class CacheManager:
    """
    Two caches:
    1. EMBEDDING CACHE: Skip re-embedding the same text
    2. RESPONSE CACHE: Skip full RAG pipeline for repeated questions
    
    Cache keys are hashed to avoid storing long strings.
    TTL: 1 hour for responses, 7 days for embeddings.
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = redis.from_url(redis_url)
    
    # --- Embedding Cache ---
    
    async def get_embedding(self, text: str) -> Optional[list]:
        key = f"emb:{hashlib.md5(text.encode()).hexdigest()}"
        cached = await self.redis.get(key)
        if cached:
            return json.loads(cached)
        return None
    
    async def set_embedding(self, text: str, embedding: list):
        key = f"emb:{hashlib.md5(text.encode()).hexdigest()}"
        await self.redis.setex(key, 7 * 24 * 3600, json.dumps(embedding))
    
    # --- Response Cache ---
    
    async def get_response(self, query: str) -> Optional[dict]:
        # Normalize query before caching
        normalized = " ".join(query.lower().strip().split())
        key = f"resp:{hashlib.md5(normalized.encode()).hexdigest()}"
        cached = await self.redis.get(key)
        if cached:
            return json.loads(cached)
        return None
    
    async def set_response(self, query: str, response: dict):
        normalized = " ".join(query.lower().strip().split())
        key = f"resp:{hashlib.md5(normalized.encode()).hexdigest()}"
        # Only cache if we got a real answer (not fallback)
        if response.get("sources"):
            await self.redis.setex(key, 3600, json.dumps(response))
    
    async def invalidate_responses(self):
        """Call after ingesting new documents"""
        async for key in self.redis.scan_iter("resp:*"):
            await self.redis.delete(key)
```

---

## Phase 15 — Evaluation & Observability

### 15.1 Why Evaluation is Non-Negotiable

Without evaluation, you don't know:
- Is your chunking producing good retrieval?
- Is the LLM hallucinating?
- Did your last code change make things better or worse?

### 15.2 RAGAS Evaluation (Free Framework)

```python
# evaluation/ragas_eval.py
"""
RAGAS metrics:
- faithfulness: Does the answer stick to the retrieved context?
- answer_relevancy: Is the answer actually answering the question?
- context_recall: Did retrieval find all relevant information?
- context_precision: Are the retrieved chunks actually relevant?
"""

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_recall, context_precision

def run_ragas_evaluation(qa_pairs: list, pipeline) -> dict:
    """
    qa_pairs: list of {"question": ..., "ground_truth": ...}
    Returns RAGAS scores.
    """
    questions, answers, contexts, ground_truths = [], [], [], []
    
    for pair in qa_pairs:
        result = pipeline.query(pair["question"], user_id="eval")
        
        questions.append(pair["question"])
        answers.append(result["answer"])
        contexts.append([chunk["text"] for chunk in result.get("chunks", [])])
        ground_truths.append(pair["ground_truth"])
    
    dataset = Dataset.from_dict({
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths
    })
    
    # Uses local LLM (via Ollama) for evaluation — fully free
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_recall, context_precision]
    )
    
    return result
```

### 15.3 Custom Metrics Logging

```python
# backend/app/evaluation/logging.py
from sqlalchemy import text
import json

class EvalLogger:
    
    def __init__(self, db_session):
        self.db = db_session
    
    async def log(self, query, processed_query, retrieved_chunks, 
                  final_chunks, answer, sources, latency_ms, user_id):
        
        await self.db.execute(text("""
            INSERT INTO query_logs 
            (query, processed_query, num_retrieved, num_final, answer, 
             sources, latency_ms, user_id, created_at)
            VALUES 
            (:query, :processed, :num_retrieved, :num_final, :answer,
             :sources, :latency, :user_id, NOW())
        """), {
            "query": query,
            "processed": json.dumps(vars(processed_query)),
            "num_retrieved": len(retrieved_chunks),
            "num_final": len(final_chunks),
            "answer": answer,
            "sources": json.dumps(sources),
            "latency": latency_ms,
            "user_id": user_id
        })
```

### 15.4 Prometheus Metrics

```python
# backend/app/core/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Track every query
query_counter = Counter("rag_queries_total", "Total queries", ["intent", "from_cache"])
query_latency = Histogram("rag_query_latency_seconds", "Query latency", buckets=[0.5, 1, 2, 5, 10])
chunks_retrieved = Histogram("rag_chunks_retrieved", "Chunks retrieved per query", buckets=[1, 5, 10, 20])

# Track ingestion
docs_ingested = Counter("rag_docs_ingested_total", "Total docs ingested", ["source_type"])
ingestion_errors = Counter("rag_ingestion_errors_total", "Ingestion errors", ["error_type"])

# System health
vector_db_size = Gauge("rag_vector_db_size", "Number of vectors in DB")
```

---

## Phase 16 — Auth & Multi-User

### 16.1 JWT Authentication

```python
# backend/app/core/security.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta

pwd_context = CryptContext(schemes=["bcrypt"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

def create_token(user_id: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=30)
    return jwt.encode(
        {"sub": user_id, "role": role, "exp": expire},
        settings.SECRET_KEY,
        algorithm="HS256"
    )

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
        role = payload.get("role", "user")
        return {"id": user_id, "role": role}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_admin_user(user = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
```

### 16.2 Department-Level Access Control

```python
# Concept: Users only see documents from their department (+ company-wide)
# Implemented via Qdrant payload filtering

async def retrieve_with_access_control(query, user):
    """
    HR employees see HR docs + company-wide docs
    IT employees see IT docs + company-wide docs
    Admins see everything
    """
    if user["role"] == "admin":
        filters = {}  # No filter
    else:
        filters = {
            "department__in": [user["department"], "company-wide"]
        }
    
    return await retriever.retrieve(query, filters=filters)
```

---

## Phase 17 — Scaling Strategy

### 17.1 Scaling Path (Free to Paid)

```
STAGE 1: SINGLE MACHINE (Portfolio Demo)
  All services on one Docker Compose
  Handles: 1-10 concurrent users
  Cost: $0 (local) or ~$20/mo VPS

STAGE 2: SEPARATED SERVICES (Small Team)
  - Qdrant on dedicated server (or Qdrant Cloud free tier)
  - Multiple backend instances behind Nginx
  - Redis Cluster for cache
  Cost: $50-100/mo

STAGE 3: PRODUCTION SCALE
  - Kubernetes (K3s — free)
  - Load balancer (Nginx or Traefik)
  - Distributed Qdrant
  - GPU server for embeddings
  Cost: Depends on traffic
```

### 17.2 Performance Optimization Checklist

```
RETRIEVAL OPTIMIZATION:
  □ Tune HNSW ef parameter (search speed vs accuracy)
  □ Enable Qdrant quantization (reduces memory 4x)
  □ Pre-filter with metadata before vector search
  □ Cache embeddings for repeated queries

INGESTION OPTIMIZATION:
  □ Batch embeddings (32 at a time, not 1 by 1)
  □ Parallel chunk processing
  □ Background workers (Celery) for large files
  □ Deduplication before embedding

LLM OPTIMIZATION:
  □ Use smaller model for simple queries (intent routing)
  □ Cache responses for common questions
  □ Use streaming to reduce perceived latency
  □ Context compression (summarize long contexts)
```

---

## Data Flow Diagrams

### Complete Ingestion Flow

```
FILE UPLOAD / URL
        │
        ▼
   File Type?
   ┌───┼───┐
  PDF DOCX HTML
   │   │   │
   └───┴───┘
        │
        ▼
  Parse + Extract
  (text, headings, metadata)
        │
        ▼
  Text Cleaner
  (remove noise, normalize)
        │
        ▼
  Content Hash Check ──→ EXISTS? → Skip (dedup)
        │ NEW
        ▼
  Chunker (structural first)
  ┌─────────────────────────┐
  │ Section 1 (chunk 1)     │
  │ Section 1 (chunk 2)     │
  │ Section 2 (chunk 3)     │
  │ ...                     │
  └─────────────────────────┘
        │
        ▼
  Embedder (batch)
  [vector1, vector2, ...]
        │
        ▼
  ┌─────────────┐
  │  Qdrant     │  ← Store vectors + payload
  └─────────────┘
        │
        ▼
  ┌─────────────┐
  │ PostgreSQL  │  ← Log doc metadata, status
  └─────────────┘
        │
        ▼
  Trigger BM25 index rebuild (Celery task)
```

### Complete Query Flow

```
USER QUERY: "What is our work from home policy?"
        │
        ▼
  Redis Cache Check ──→ HIT? → Return cached response
        │ MISS
        ▼
  Query Processor
  ├── Intent: "factual"
  ├── Rewritten: "work from home policy employee"
  ├── Filters: {department: "HR"}
  └── Expand: ["remote work", "WFH", "telecommute"]
        │
        ▼
  ┌─────────────────────────────┐
  │      HYBRID RETRIEVAL       │
  │  ┌──────────────────────┐   │
  │  │ Dense: Qdrant search  │   │
  │  │ → 20 results          │   │
  │  └──────────────────────┘   │
  │  ┌──────────────────────┐   │
  │  │ Sparse: BM25 search   │   │
  │  │ → 20 results          │   │
  │  └──────────────────────┘   │
  │         ↓                   │
  │   RRF Merge → 20 unique     │
  └─────────────────────────────┘
        │
        ▼
  Cross-Encoder Reranker
  → Top 5 most relevant chunks
        │
        ▼
  Context Builder
  → Deduplicate, format, add source labels
  → Stay within 3000 token budget
        │
        ▼
  Prompt Assembly
  [System: RAG rules]
  [Context: 5 chunks]
  [Query: user question]
        │
        ▼
  Ollama LLM (Mistral 7B)
  → Grounded answer with [Source N] citations
        │
        ▼
  Cache response in Redis
        │
        ▼
  Log to PostgreSQL (for eval)
        │
        ▼
  Stream to Frontend → User sees answer
```

---

## The Master Prompt Collection

### Prompt 1: Initial Architecture Review

```
You are a senior RAG systems architect. I am building a production-grade RAG company 
assistant with the following stack: Ollama (Mistral 7B), sentence-transformers (BGE-M3), 
Qdrant, FastAPI, Next.js, Redis, Celery, PostgreSQL — all self-hosted for zero cost.

My data sources: internal PDFs, DOCX files, and scraped internal documentation pages.
Expected load: 50-100 employees, 200-500 queries/day.

Review my architecture for:
1. Single points of failure
2. Performance bottlenecks I haven't addressed
3. Gaps in my retrieval quality strategy
4. Missing components for production readiness

Be specific and prioritize by impact.
```

### Prompt 2: Chunking Optimization

```
I am chunking company documentation for a RAG system. My current approach:
- Structural chunker (split by headings)
- Sliding window (512 tokens, 50 token overlap) for long sections
- Semantic chunker for unstructured web content

My documents include: HR policy PDFs (structured), IT support pages (structured), 
employee handbooks (semi-structured), and FAQ pages (Q&A format).

For each document type, give me:
1. The optimal chunking strategy and why
2. The ideal chunk size for this content type
3. What metadata to preserve with each chunk
4. Any special handling needed

Focus on retrieval quality, not ingestion speed.
```

### Prompt 3: Retrieval Quality Debugging

```
My RAG system is returning irrelevant results for some queries. Help me debug.

Query: "How many sick days do I get per year?"
Expected: HR policy about sick leave
Actual: Retrieved chunks about general leave, vacation policy, but not specific sick days

My setup:
- BGE-M3 embeddings, 1024 dims
- Qdrant with cosine similarity
- BM25 + dense hybrid with RRF
- Cross-encoder reranker (ms-marco-MiniLM-L-6-v2)
- Chunk size: 512 tokens, 50 overlap

Diagnose possible causes and give me specific tests to identify which layer is failing.
```

### Prompt 4: Evaluation Dataset Creation

```
I need a golden evaluation dataset for my company RAG assistant.
My knowledge base contains: HR policies, IT procedures, finance guidelines, and product docs.

Generate a diverse set of 20 test questions covering:
- Simple factual questions (5)
- Procedural questions (5)  
- Policy questions requiring exact numbers/dates (5)
- Multi-hop questions requiring combining two pieces of information (5)

For each question, specify:
- The question
- The expected answer type (fact/procedure/policy)
- What a GOOD answer looks like
- Common failure modes to test for (hallucination, partial answers, etc.)

Format as JSON.
```

### Prompt 5: Production Hardening

```
My RAG system works in development. Now I need to harden it for production.

Current state: Single Docker Compose, all services on one machine, no monitoring.
Target: Reliable, observable system for 100 daily users.

Give me a prioritized checklist covering:
1. Reliability (what breaks, how to prevent it)
2. Observability (what to monitor and alert on)
3. Security (auth, input validation, rate limiting)
4. Data freshness (how to handle document updates)
5. Graceful degradation (what happens when Ollama is slow?)

For each item: what it is, why it matters, and the simplest implementation.
```

---

## Portfolio Presentation Guide

### What to Highlight to Recruiters/Interviewers

#### The Story (30-second version)
> "I built a production-grade RAG system from scratch — no paid APIs. It ingests company documents, uses hybrid search combining vector similarity and BM25, reranks with a cross-encoder, and streams answers to a Next.js frontend. The whole thing runs on Docker Compose."

#### Technical Depth You Can Speak To

| Topic | Your Answer |
|-------|-------------|
| "Why hybrid retrieval?" | Dense search captures semantic meaning; BM25 catches exact keyword matches. RRF merges them without needing to normalize scores. |
| "How do you handle hallucination?" | Strict system prompt + only citing retrieved sources + confidence thresholding |
| "Why Qdrant over Chroma?" | HNSW config control, payload filtering, production-ready, Docker-native |
| "How do you evaluate quality?" | RAGAS framework: faithfulness, relevancy, context recall, precision |
| "What's your chunking strategy?" | Structural-first (preserves section context), sliding window fallback, semantic for unstructured |

#### Demo Flow (5 minutes)
1. Show the chat UI — ask a policy question → streamed answer + sources
2. Show admin panel — upload a new document → watch it ingest
3. Show Grafana dashboard — latency, chunk counts, query volume
4. Show code — walk through the RAG pipeline class
5. Show evaluation — RAGAS scores, query logs

#### GitHub README Must Include
- Architecture diagram (the ASCII one from this doc)
- Docker Compose one-liner to run everything
- Tech stack table with rationale
- RAGAS evaluation scores (your baseline)
- Screenshots of the UI and Grafana dashboard

---

## Quick Reference: Phase Checklist

```
PHASE 0  □ Docker Compose with all services
         □ Folder structure created
         □ Config management (Pydantic Settings)
         □ .env.example committed

PHASE 1  □ Scrapy spider for static docs
         □ Playwright scraper for JS sites
         □ Direct file ingestion path

PHASE 2  □ PDF parser (PyMuPDF)
         □ HTML parser (BeautifulSoup)
         □ DOCX parser (python-docx)
         □ Text cleaner pipeline
         □ Deduplication (content hash)

PHASE 3  □ Sliding window chunker
         □ Structural chunker
         □ Semantic chunker
         □ Hierarchical chunker (optional, for key docs)

PHASE 4  □ BGE-M3 embedder
         □ Batch embedding pipeline
         □ Query prefix handling (BGE models)

PHASE 5  □ Qdrant collection with HNSW config
         □ Payload indexes for filtering
         □ Upsert with metadata

PHASE 6  □ BM25 index (rank_bm25)
         □ Dense retrieval (Qdrant)
         □ RRF fusion
         □ Multi-query (optional)

PHASE 7  □ Cross-encoder reranker
         □ Score threshold filtering

PHASE 8  □ Intent detection
         □ Query rewriting
         □ Filter extraction

PHASE 9  □ Ollama client (async + streaming)
         □ Context builder (dedup + token budget)
         □ RAG system prompt
         □ Fallback response

PHASE 10 □ RAG pipeline orchestrator
         □ Cache integration
         □ Eval logging

PHASE 11 □ FastAPI app
         □ Query endpoint (sync + streaming SSE)
         □ Ingest endpoint
         □ Auth middleware

PHASE 12 □ Next.js chat UI
         □ Streaming token rendering
         □ Source citation display
         □ Admin upload panel

PHASE 13 □ Celery workers
         □ Document processing task
         □ BM25 rebuild task

PHASE 14 □ Redis embedding cache
         □ Redis response cache
         □ Cache invalidation on ingest

PHASE 15 □ RAGAS evaluation
         □ Golden QA dataset (20+ pairs)
         □ Prometheus metrics
         □ Grafana dashboards

PHASE 16 □ JWT auth
         □ User roles (admin/user)
         □ Department-based filtering

PHASE 17 □ Health check endpoints
         □ Nginx reverse proxy config
         □ Production env vars
         □ README with architecture + setup
```

---

*Built with: Ollama • Qdrant • BGE-M3 • FastAPI • Next.js • Celery • Redis • PostgreSQL • RAGAS*
*Cost: $0 in API fees. Real production architecture. Portfolio-ready.*
