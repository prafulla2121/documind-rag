# 🧠 DocuMind – RAG-Powered Document Q&A System

> Upload PDFs. Ask questions. Get answers with source citations — powered by LangChain, FAISS, and Claude.

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://python.org)
[![LangChain](https://img.shields.io/badge/LangChain-0.1.20-green)](https://langchain.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.32-red)](https://streamlit.io)
[![Claude](https://img.shields.io/badge/Claude-Anthropic-orange)](https://anthropic.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📌 Overview

DocuMind is a production-grade **Retrieval-Augmented Generation (RAG)** system that lets you upload multiple PDF documents and ask natural language questions about them. It uses semantic search powered by FAISS to retrieve relevant context, then feeds it to Claude (Anthropic) for accurate, grounded answers with source citations.

---

## ✨ Features

- 📄 **Multi-Document Support** — Upload and query multiple PDFs simultaneously
- 🔍 **Semantic Search** — HuggingFace embeddings + FAISS vector store
- 🤖 **Claude LLM** — Context-grounded answers via Anthropic's Claude API
- 🧠 **Conversation Memory** — LangChain ConversationBufferMemory for multi-turn Q&A
- 📎 **Source Citations** — Answers grounded in retrieved document chunks
- 🚀 **REST API** — FastAPI endpoint for programmatic access
- 🐳 **Docker Ready** — Containerized for easy deployment

---

## 🏗️ Architecture

```
PDF Files → Text Extraction (PyPDF2)
         → Text Chunking (CharacterTextSplitter)
         → Embeddings (HuggingFace: all-MiniLM-L6-v2)
         → FAISS Vector Index
         
User Query → Embed Query
           → FAISS Semantic Search (top-k chunks)
           → LangChain ConversationalRetrievalChain
           → Claude LLM (claude-3-haiku)
           → Answer + Source Citations
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Claude (Anthropic) / OpenAI GPT |
| Embeddings | HuggingFace `all-MiniLM-L6-v2` |
| Vector Store | FAISS |
| RAG Framework | LangChain |
| UI | Streamlit |
| API | FastAPI |
| Deployment | AWS EC2 + Nginx / Hugging Face Spaces |
| CI/CD | GitHub Actions |

---

## 🚀 Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/prafulla2121/documind-rag.git
cd documind-rag
```

### 2. Create virtual environment
```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Add API keys
Create a `.env` file:
```
ANTHROPIC_API_KEY=your_anthropic_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
```

### 5. Run the app
```bash
streamlit run app.py
```
Open `http://localhost:8501` in your browser.

### 6. Run the API (optional)
```bash
uvicorn api:app --reload --port 8000
```
Swagger docs at `http://localhost:8000/docs`

---

## 🐳 Docker

```bash
docker build -t documind .
docker run -p 8501:8501 --env-file .env documind
```

---

## 📁 Project Structure

```
documind-rag/
├── app.py              # Streamlit UI + RAG pipeline
├── api.py              # FastAPI REST endpoint
├── htmlTemplates.py    # UI templates
├── requirements.txt    # Dependencies
├── Dockerfile          # Container config
├── .env.example        # Environment template
├── .gitignore
└── README.md
```

---

## 📸 Demo

> Upload 1–5 PDF files → Click "Process Documents" → Ask any question!

Example queries:
- *"What is the main argument of this paper?"*
- *"Summarize the key findings in section 3"*
- *"What methodology was used?"*

---

## 🤝 Contributing

Pull requests are welcome! For major changes, open an issue first.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) file.

---

## 👤 Author

**Prafulla Purohit**  
🔗 [LinkedIn](https://linkedin.com/in/prafulla-purohit) | [GitHub](https://github.com/prafulla2121)
