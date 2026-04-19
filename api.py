from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_anthropic import ChatAnthropic
from langchain.chains import RetrievalQA
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI(
    title="DocuMind API",
    description="RAG-powered Document Q&A REST API",
    version="1.0.0"
)


class QueryRequest(BaseModel):
    question: str
    index_path: str = "faiss_index"


class QueryResponse(BaseModel):
    answer: str
    source_documents: list


@app.get("/")
def root():
    return {"message": "DocuMind RAG API is running!", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/query", response_model=QueryResponse)
def query_documents(request: QueryRequest):
    try:
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )

        if not os.path.exists(request.index_path):
            raise ValueError(f"Index path '{request.index_path}' does not exist.")

        vectorstore = FAISS.load_local(request.index_path, embeddings)

        qa = RetrievalQA.from_chain_type(
            llm=ChatAnthropic(
                model="claude-3-haiku-20240307",
                anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
                temperature=0.3,
            ),
            chain_type="stuff",
            retriever=vectorstore.as_retriever(),
            return_source_documents=True,
        )

        result = qa({"query": request.question, "return_source_documents": True})
        sources = [
            {"page_content": doc.page_content, "metadata": doc.metadata}
            for doc in result.get("source_documents", [])
        ]

        return QueryResponse(answer=result["result"], source_documents=sources)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
