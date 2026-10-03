from __future__ import annotations
from pathlib import Path
import streamlit as st
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from app.config import CONFIG

@st.cache_resource
def get_embedding_model():
    return HuggingFaceEmbeddings(model_name=CONFIG["embedding_model_name"])

def get_vectorstore_signature(vectorstore_dir: str) -> str:
    base=Path(vectorstore_dir)
    if not base.exists():return "missing"
    parts=[]
    for path in sorted(base.rglob("*")):
        if path.is_file():parts.append(f"{path.relative_to(base)}:{path.stat().st_size}")
    return "|".join(parts)

@st.cache_resource
def get_vectorstore_cached(signature: str):
    return Chroma(
        collection_name=CONFIG.get("collection_name","langchain"),
        persist_directory=CONFIG["vectorstore_dir"],
        embedding_function=get_embedding_model(),
    )

def get_vectorstore():
    vectorstore_dir=CONFIG["vectorstore_dir"]
    if not Path(vectorstore_dir).exists():
        raise FileNotFoundError(f"Vector store directory not found: {vectorstore_dir}")
    return get_vectorstore_cached(get_vectorstore_signature(vectorstore_dir))
