# DocuMind RAG

**Chat with your own documents.** Upload PDFs, Word files, web pages or YouTube videos, then ask questions and get answers with source citations — using a hybrid (vector + BM25) retrieval pipeline and the LLM of your choice.

## Architecture

```mermaid
flowchart LR
    subgraph Ingestion
        A[PDF / DOCX / TXT / MD] --> P[Parsers]
        U[URL / Sitemap] --> P
        Y[YouTube transcript] --> P
        P --> C[Text cleaner]
        C --> K{Chunker<br/>structural · sliding window · semantic}
        K --> E[Embedder<br/>all-MiniLM-L6-v2]
        E --> Q[(Qdrant<br/>local file mode)]
        K --> B[(BM25 index)]
    end

    subgraph Query
        UQ[User question] --> QP[Query processor<br/>rewrite + intent]
        QP --> MQ[Multi-query expansion]
        MQ --> HR[Hybrid retriever<br/>dense + BM25, RRF merge]
        Q --> HR
        B --> HR
        HR --> RR[Cross-encoder reranker<br/>ms-marco-MiniLM-L-6-v2]
        RR --> CC[Context compressor]
        CC --> LLM[LLM provider<br/>OpenAI · Anthropic · Gemini · Ollama<br/>+ OpenAI-compatible: Groq, Mistral, custom]
        LLM --> ANS[Answer + sources<br/>streamed over SSE]
    end

    FE[React + Vite UI] <--> API[FastAPI /api]
    API --> Ingestion
    API --> Query
    API --> DB[(SQL metadata DB<br/>users · sessions · documents)]
    API --> CA[(Cache<br/>Redis or in-memory)]
```

## Features

- **Many sources** — PDF, DOCX, HTML/URL, whole sitemaps, and YouTube transcripts.
- **Three chunkers** — structural (heading-aware) with a sliding-window fallback for files; sliding window, structural or semantic can be chosen for YouTube ingestion.
- **Hybrid retrieval** — dense vectors in Qdrant + BM25 sparse search, merged with Reciprocal Rank Fusion.
- **Query transformation** — the question is refined, its intent is detected (chit-chat is short-circuited), and it is expanded into extra search queries.
- **Cross-encoder reranking** and TF-IDF based **context compression** before the LLM call.
- **Bring your own LLM** — provider classes for OpenAI, Anthropic, Gemini and Ollama; Groq, Mistral and any OpenAI-compatible endpoint go through the OpenAI client. Users pick a model in the UI; API keys are stored encrypted (Fernet).
- **Streaming answers** over Server-Sent Events, with a phase indicator and source citations.
- **Chat sessions** — history, rename, pin, search, delete, message edit and feedback; long histories are summarised before they are sent to the LLM.
- **Auth** — username/password with JWT, plus Google sign-in.
- **Per-user settings** — custom system prompt and RAG settings (`top_k`, `rerank_k`).
- **Observability** — per-stage timings, JSON trace logs, response and embedding cache, admin stats and BM25 rebuild endpoints.
- **Eval suite** — 15-question golden set over a sample document; scores retrieval (hit rate, MRR), whether the evidence survives context compression, and answer faithfulness / relevance with an LLM judge. Runs in CI with a stub LLM, no API keys.
- **MCP server** — `ingest_document`, `query` and `list_documents` as MCP tools over stdio, so Claude Desktop, Claude Code or any MCP client can use DocuMind directly.

## Tech stack

| Layer | Tools |
| --- | --- |
| Backend | Python, FastAPI, Uvicorn, Pydantic Settings, SQLAlchemy (async) |
| Retrieval | sentence-transformers, Qdrant (local mode), rank_bm25, CrossEncoder, NLTK / scikit-learn |
| LLMs | OpenAI, Anthropic, Google Gemini, Ollama SDKs / HTTP |
| Ingestion | PyMuPDF, python-docx, BeautifulSoup + lxml, youtube-transcript-api, yt-dlp |
| Storage | PostgreSQL (asyncpg) or SQLite (aiosqlite), optional Redis |
| Frontend | React 19, Vite, react-markdown, @react-oauth/google |

## Quick start

Needs Python 3.10+ and Node.js 18+. For a fully local setup also install [Ollama](https://ollama.com) and run `ollama pull llama3`.

```bash
# 1. Config — copy the example and edit it
cp .env.example .env
# The default DATABASE_URL is PostgreSQL. For a no-server setup add:
#   DATABASE_URL=sqlite+aiosqlite:///./data/metadata.db

# 2. Backend (terminal 1)
python -m venv venv
source venv/bin/activate          # Windows: .\venv\Scripts\activate
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 3. Frontend (terminal 2)
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. API docs are at http://localhost:8000/api/docs.

All local data (vectors, BM25 index, uploads) is stored in `data/`. Delete that folder to reset.

## Evals

`evals/run_evals.py` ingests [`evals/harbor_lamp_guide.md`](evals/harbor_lamp_guide.md) (a short fictional product guide, CC0) into a temporary index, runs the 15 questions in [`evals/golden.jsonl`](evals/golden.jsonl) through the real retriever, reranker and `RAGPipeline`, and writes `evals/report.md`.

| Metric | What it measures |
| --- | --- |
| `hit_rate_at_1`, `hit_rate_at_5`, `mrr` | Is the chunk holding the answer's evidence ranked at the top after hybrid retrieval + reranking? |
| `evidence_survives_compression` | Is the evidence still in the compressed context that the LLM actually sees? |
| `answered_from_docs` | Share of questions answered from retrieved chunks (not chit-chat or fallback). |
| `faithfulness`, `relevance` | LLM-as-judge scores (0–1) from `RAGEvaluator` in `app/rag/observability.py`, using the same provider layer. |

```bash
pip install -r backend/requirements.txt

# No keys, no model server: real retrieval, stub LLM (judge skipped). This is what CI runs.
python evals/run_evals.py --provider stub --min-hit-rate 0.9

# Real local model as answerer and judge
ollama pull llama3.2:3b
python evals/run_evals.py --provider ollama --model llama3.2:3b

# Any other provider from app/providers/registry.py
LLM_API_KEY=... python evals/run_evals.py --provider openai --model gpt-4o-mini
```

Stub-mode result on this repo (Python 3.12, CPU):

| hit_rate_at_1 | hit_rate_at_5 | mrr | evidence_survives_compression | answered_from_docs |
| --- | --- | --- | --- | --- |
| 0.93 | 1.00 | 0.97 | 0.80 | 1.00 |

What the evals found on their first run, and what was fixed:

- Every query crashed on a fresh install: NLTK 3.9 needs the `punkt_tab` data, but the compressor downloaded `punkt`. Fixed.
- The chit-chat check matched `hi` inside words, so "Which light mode…" and "How bright is High mode…" got the greeting reply instead of an answer (`answered_from_docs` was 0.87). Fixed with word boundaries; now 1.00.
- Still open: the context compressor keeps only 5 sentences, and for 3 of 15 questions it drops the sentence with the answer even though retrieval ranked it first.

The CI workflow for this (pytest + stub-mode evals on every push, fails if `hit_rate_at_5` drops below 0.9) is committed separately; see the `ci:` commit.

## MCP server

[`mcp_server/server.py`](mcp_server/server.py) exposes DocuMind as [Model Context Protocol](https://modelcontextprotocol.io) tools over stdio, using the official `mcp` Python SDK (FastMCP). It calls the ingestion and RAG pipelines in-process — no HTTP server needed.

| Tool | What it does |
| --- | --- |
| `ingest_document(path)` | Parse, chunk, embed and index a local pdf / docx / html / txt / md / csv file. Only files under `DOCUMIND_MCP_ROOT` are allowed. |
| `query(question, top_k=10)` | Hybrid retrieval → rerank → compress → LLM answer, with sources. |
| `list_documents()` | Documents in the index (title, doc_id, chunk count). |

Settings (environment variables):

| Variable | Default | Purpose |
| --- | --- | --- |
| `DOCUMIND_LLM_PROVIDER` | `ollama` | Any provider in `app/providers/registry.py` |
| `DOCUMIND_LLM_MODEL` | `LLM_MODEL` (`llama3`) | Model name |
| `DOCUMIND_LLM_API_KEY` / `DOCUMIND_LLM_BASE_URL` | — | For hosted providers / custom endpoints |
| `DOCUMIND_MCP_ROOT` | your home folder | Only files under this folder can be ingested |
| `DOCUMIND_USER_ID` | `anonymous` | Index namespace the tools read and write |

**Claude Desktop** — add to `claude_desktop_config.json` (use absolute paths; on Windows the venv Python is `venv\Scripts\python.exe`):

```json
{
  "mcpServers": {
    "documind": {
      "command": "/abs/path/to/documind-rag/venv/bin/python",
      "args": ["/abs/path/to/documind-rag/mcp_server/server.py"],
      "env": {
        "DOCUMIND_LLM_PROVIDER": "ollama",
        "DOCUMIND_LLM_MODEL": "llama3.2:3b",
        "DOCUMIND_MCP_ROOT": "/abs/path/to/your/docs"
      }
    }
  }
}
```

**Claude Code**:

```bash
claude mcp add --transport stdio \
  --env DOCUMIND_LLM_PROVIDER=ollama --env DOCUMIND_LLM_MODEL=llama3.2:3b \
  --env DOCUMIND_MCP_ROOT=/abs/path/to/your/docs \
  documind -- /abs/path/to/documind-rag/venv/bin/python /abs/path/to/documind-rag/mcp_server/server.py
```

The tests in `tests/test_mcp_server.py` drive the server through a real MCP client session (in memory): list tools, ingest the sample doc, list it, query it (stub LLM), and check that paths outside `DOCUMIND_MCP_ROOT` and unsupported file types are rejected.

## Tests

```bash
pip install -r backend/requirements.txt
pytest tests -q
```

## Environment variables

From [`.env.example`](.env.example):

| Variable | Default | Purpose |
| --- | --- | --- |
| `OLLAMA_URL` | `http://localhost:11434` | Local Ollama server |
| `LLM_MODEL` | `llama3` | Default model |
| `LLM_TEMPERATURE` | `0.1` | Low for factual answers |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | sentence-transformers model |
| `QDRANT_PATH` / `QDRANT_COLLECTION` | `./data/qdrant_storage` / `company_docs` | Vector store location |
| `TOP_K_DENSE` / `TOP_K_SPARSE` / `TOP_K_FINAL` | `20` / `20` / `5` | Retrieval sizes |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `512` / `50` | Chunking |
| `SECRET_KEY` | — | JWT signing key — **change it** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Token lifetime |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | — | Google sign-in (optional) |
| `VITE_GOOGLE_CLIENT_ID` | — | Google client ID for the frontend |
| `BACKEND_PORT` / `FRONTEND_PORT` | `8000` / `5173` | Ports |

Also read by the backend (see `backend/app/core/config.py`): `DATABASE_URL`, `REDIS_URL` (optional, in-memory cache if empty) and `ENCRYPTION_KEY` (encrypts stored API keys — set your own).

## Project structure

```
backend/
  app/
    api/routes/      auth, query (chat + sessions), ingest, models, admin
    core/            config, JWT security, Fernet key vault
    ingestion/       parsers (pdf, docx, html, youtube), cleaner, chunkers, embedder, pipeline
    rag/             query processor/transformer, hybrid retriever, BM25, reranker,
                     compressor, context builder, prompts, observability, pipeline
    providers/       OpenAI, Anthropic, Gemini, Ollama + model catalog
    storage/         Qdrant vector store, SQL metadata DB, cache
evals/               golden set, sample doc, eval runner (run_evals.py)
mcp_server/          MCP server (server.py)
tests/               pytest suite for evals and the MCP server
frontend/            React + Vite chat UI
app.py, api.py       first version: Streamlit + LangChain + FAISS demo (kept for reference)
```
