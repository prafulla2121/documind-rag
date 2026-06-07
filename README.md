# Local-First RAG Company Assistant

A fully local, production-grade Retrieval-Augmented Generation (RAG) assistant designed for parsing, embedding, and chatting with company documents locally without any Docker dependencies.

## Features
- **Local-First AI**: Connects natively to local LLMs via Ollama.
- **Embedded Database**: Uses Qdrant in Local File Mode + SQLite (No external DB servers required).
- **Hybrid Search**: Fuses Dense Vector embeddings (`sentence-transformers`) with Sparse Retrieval (BM25) and Cross-Encoder reranking.
- **Beautiful UI**: React + Vite frontend mimicking modern, clean AI chat interfaces.
- **Session Memory**: Built-in chat history state management and recall.

---

## 🛠️ Prerequisites

Before running the project, make sure you have the following installed:
1. **Python 3.10+**
2. **Node.js v18+**
3. **Ollama** (Running locally on port `11434` with the `llama3` model downloaded)

To download the LLM model via Ollama, open a terminal and run:
```bash
ollama pull llama3
```

---

## 🚀 How to Run the Project

You will need to open **two** separate terminal windows—one for the Backend and one for the Frontend.

### Terminal 1: Start the FastAPI Backend

1. Open a terminal and navigate to the root directory of the project.
2. Create and activate a Python virtual environment (if you haven't already):
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   ```
3. Install the required Python dependencies:
   ```powershell
   cd backend
   pip install -r requirements.txt
   ```
4. Start the FastAPI server using Uvicorn:
   ```powershell
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
   *(Wait until you see `✅ RAG Company Assistant is ready!` in the console before moving to the next step).*

### Terminal 2: Start the React Frontend

1. Open a new terminal and navigate to the `frontend` folder:
   ```powershell
   cd frontend
   ```
2. Install the Node.js dependencies (only needed the first time):
   ```powershell
   npm install
   ```
3. Start the Vite development server:
   ```powershell
   npm run dev
   ```

---

## 💻 Usage

Once both servers are running:
1. Open your web browser and navigate to **http://localhost:5173**.
2. Click the **Upload Documents** tab to drag and drop PDFs, DOCX, or paste URLs to scrape.
3. Switch back to the **Current Chat** tab and ask the assistant questions based on your uploaded knowledge base.

*Note: All data (vectors, SQLite databases, and BM25 indices) is saved natively inside the `backend/data/` folder. To reset the application completely, simply delete the `data` folder and restart the backend.*
