# app/config.py
# Centralized configuration for Arus PrintAssist

from pathlib import Path

# -----------------------------------------------------------------------------
# Project paths
# -----------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PDF_DIR = DATA_DIR / "knowledge_base_pdfs"
VECTORSTORE_DIR = DATA_DIR / "vectorstore"
RUNTIME_DIR = DATA_DIR / "runtime"

# Ensure expected folders exist
PDF_DIR.mkdir(parents=True, exist_ok=True)
VECTORSTORE_DIR.mkdir(parents=True, exist_ok=True)
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

# -----------------------------------------------------------------------------
# Streamlit UI configuration
# -----------------------------------------------------------------------------
APP_TITLE = "Arus PrintAssist"
APP_SUBTITLE = (
    "Asistente de soporte de impresión, documentación técnica "
    "y escalamiento de incidentes."
)
PAGE_ICON = "🖨️"
PAGE_LAYOUT = "wide"
SIDEBAR_TITLE = "Control de sesión"

# -----------------------------------------------------------------------------
# Backend configuration
# -----------------------------------------------------------------------------
CONFIG = {
    "project_name": "Arus PrintAssist Prototype",
    "language": "es",
    "embedding_model_name": "sentence-transformers/all-MiniLM-L6-v2",
    "vectorstore_dir": str(VECTORSTORE_DIR),
    "chunk_size": 800,
    "chunk_overlap": 150,
    "retrieval_top_k": 4,
    "pdf_dir": str(PDF_DIR),
    "runtime_dir": str(RUNTIME_DIR),
}

LLM_CONFIG = {
    "model_name": "Qwen/Qwen2.5-7B-Instruct",
    "temperature": 0.2,
    "max_tokens": 500,
}
