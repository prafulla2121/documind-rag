import os

import streamlit as st
from PyPDF2 import PdfReader
from dotenv import load_dotenv
from langchain.text_splitter import CharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_anthropic import ChatAnthropic
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain
from htmlTemplates import css, bot_template, user_template

load_dotenv()

st.set_page_config(
    page_title="DocuMind – RAG Document Q&A",
    page_icon="🧠",
    layout="wide"
)

st.markdown(
    """
    <style>
        .main-header {
            font-size: 2.5rem;
            font-weight: 700;
            color: #0f172a;
            padding: 1rem 0;
        }
        .sub-header {
            font-size: 1rem;
            color: #334155;
            margin-bottom: 1.5rem;
        }
        .sidebar .stButton>button {
            width: 100%;
            background-color: #2563eb;
            color: white;
            border: none;
            border-radius: 0.5rem;
            padding: 0.8rem 1rem;
        }
        .sidebar .stButton>button:hover {
            background-color: #1d4ed8;
        }
        .stTextInput>div>div>input {
            border-radius: 0.75rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_pdf_text(pdf_docs):
    """Extract text from uploaded PDF files."""
    text = ""
    for pdf in pdf_docs:
        pdf_reader = PdfReader(pdf)
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text


def get_text_chunks(text):
    """Split raw text into smaller chunks for embeddings."""
    text_splitter = CharacterTextSplitter(
        separator="\n",
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
    )
    return text_splitter.split_text(text)


def get_vectorstore(text_chunks):
    """Create a FAISS index from text chunks."""
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
    return FAISS.from_texts(texts=text_chunks, embedding=embeddings)


def get_conversation_chain(vectorstore):
    """Build the conversational retrieval chain with Anthropic Claude."""
    llm = ChatAnthropic(
        model="claude-3-haiku-20240307",
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        temperature=0.3,
    )
    memory = ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True,
    )
    return ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=vectorstore.as_retriever(search_kwargs={"k": 4}),
        memory=memory,
    )


def handle_user_input(user_question):
    """Process a user question and display the chat history."""
    if st.session_state.conversation is None:
        st.warning("⚠️ Please upload and process PDFs first!")
        return

    response = st.session_state.conversation({"question": user_question})
    st.session_state.chat_history = response["chat_history"]

    for i, message in enumerate(st.session_state.chat_history):
        if i % 2 == 0:
            st.markdown(user_template.replace("{{MSG}}", message.content), unsafe_allow_html=True)
        else:
            st.markdown(bot_template.replace("{{MSG}}", message.content), unsafe_allow_html=True)


def main():
    st.markdown('<p class="main-header">🧠 DocuMind</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub-header">RAG-Powered Document Q&A | Built with LangChain + Claude + FAISS</p>',
        unsafe_allow_html=True,
    )

    if "conversation" not in st.session_state:
        st.session_state.conversation = None
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = None

    user_question = st.text_input(
        "💬 Ask a question about your documents:",
        placeholder="e.g. What is the main topic of the document?"
    )
    if user_question:
        handle_user_input(user_question)

    with st.sidebar:
        st.header("📂 Upload Documents")
        pdf_docs = st.file_uploader(
            "Upload your PDFs here", accept_multiple_files=True, type=["pdf"]
        )
        if st.button("Process Documents"):
            if not pdf_docs:
                st.warning("Please upload at least one PDF file.")
            else:
                with st.spinner("Processing documents..."):
                    raw_text = get_pdf_text(pdf_docs)
                    if not raw_text.strip():
                        st.warning("No text could be extracted from the uploaded PDFs.")
                    else:
                        text_chunks = get_text_chunks(raw_text)
                        vectorstore = get_vectorstore(text_chunks)
                        st.session_state.conversation = get_conversation_chain(vectorstore)
                        st.success("✅ Documents processed successfully! You can now ask questions.")

        st.caption("Built by Prafulla Purohit | github.com/prafulla2121")


if __name__ == '__main__':
    main()
