#!/usr/bin/env python3
"""
Build or rebuild the Arus PrintAssist Chroma vectorstore from PDF documents.

This script is a cleaned, runnable extraction of the original academic prototype
pipeline described in phase_4_advanced_llm's_and_chatbot_models.py:
PDFs -> text extraction -> chunking -> embeddings -> persistent Chroma index.

Typical usage from the repository root:

    python scripts/build_vectorstore.py \
      --pdf-dir knowledge_base_pdfs \
      --output-dir vectorstore/chroma \
      --force

For a timestamped build:

    python scripts/build_vectorstore.py \
      --pdf-dir knowledge_base_pdfs \
      --output-dir vectorstore/chroma_$(date +%Y%m%d_%H%M%S)

Requirements:
    langchain-community
    langchain-text-splitters
    langchain-huggingface
    langchain-chroma
    chromadb
    sentence-transformers
    pypdf
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings

try:
    from langchain_chroma import Chroma
except Exception:  # pragma: no cover - compatibility fallback
    from langchain_community.vectorstores import Chroma  # type: ignore


DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 150
DEFAULT_COLLECTION_NAME = "langchain"


PDF_COLLECTIONS: dict[str, dict[str, Any]] = {
    "DA Arus": {
        "vendor": "arus_internal",
        "product": "sanitized_support_assets",
        "collection_name": "DA Arus",
        "source_type": "pdf",
        "source_group": "core_support",
        "priority": 1,
        "public_or_sanitized": "sanitized",
    },
    "GAV Tracking": {
        "vendor": "gav",
        "product": "gav_tracking",
        "collection_name": "GAV Tracking",
        "source_type": "pdf",
        "source_group": "core_support",
        "priority": 1,
        "public_or_sanitized": "public",
    },
    "HP AC": {
        "vendor": "hp",
        "product": "hp_access_control",
        "collection_name": "HP AC",
        "source_type": "pdf",
        "source_group": "core_support",
        "priority": 1,
        "public_or_sanitized": "public",
    },
    "HP SDS": {
        "vendor": "hp",
        "product": "sds",
        "collection_name": "HP SDS",
        "source_type": "pdf",
        "source_group": "core_support",
        "priority": 1,
        "public_or_sanitized": "public",
    },
    "HP WJA": {
        "vendor": "hp",
        "product": "web_jetadmin",
        "collection_name": "HP WJA",
        "source_type": "pdf",
        "source_group": "core_support",
        "priority": 1,
        "public_or_sanitized": "public",
    },
}


@dataclass
class BuildStats:
    pdf_files_found: int = 0
    pdf_files_loaded: int = 0
    pdf_files_skipped: int = 0
    pages_loaded: int = 0
    chunks_created: int = 0


def normalize_text(value: str) -> str:
    return " ".join(str(value or "").strip().split())


def infer_pdf_component_and_family(filename: str, folder_name: str) -> tuple[str, str]:
    """Infer lightweight metadata from filename and source folder."""
    text = filename.lower()

    component = "general"
    document_family = "general_document"

    if "dca" in text:
        component = "dca"
    elif "sda" in text:
        component = "sda"
    elif "jamc" in text:
        component = "jamc"
    elif "monitor" in text:
        component = "monitor"
    elif "portal" in text:
        component = "portal"
    elif "security" in text or "seguridad" in text or "protocol" in text:
        component = "security"
    elif "requirement" in text or "requer" in text or "requisito" in text:
        component = "requirements"
    elif "release" in text or "highlight" in text:
        component = "release_notes"
    elif "install" in text or "instal" in text:
        component = "installation"
    elif "admin" in text or "administrator" in text:
        component = "admin"
    elif "troubleshoot" in text or "problema" in text or "troubleshooting" in text:
        component = "troubleshooting"
    elif "operación" in text or "operacion" in text:
        component = "internal_support_asset"

    if "guide" in text or "guía" in text or "guia" in text or "manual" in text:
        document_family = "guide"
    elif "release" in text or "highlight" in text:
        document_family = "release_notes"
    elif "brochure" in text or "folleto" in text:
        document_family = "brochure"
    elif "requirement" in text or "requer" in text or "requisito" in text:
        document_family = "requirements"
    elif "security" in text or "seguridad" in text:
        document_family = "security_document"
    elif "checklist" in text:
        document_family = "checklist"

    if folder_name == "DA Arus" and component == "general":
        component = "internal_support_asset"

    return component, document_family


def infer_title(pdf_path: Path) -> str:
    stem = pdf_path.stem
    stem = re.sub(r"[_]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    return stem


def get_pdf_collection_metadata(pdf_path: Path, pdf_dir: Path, include_unknown: bool = False) -> tuple[str | None, dict[str, Any] | None]:
    """Map a PDF to collection metadata based on first folder under pdf_dir."""
    relative_parts = pdf_path.relative_to(pdf_dir).parts
    folder_name = relative_parts[0] if relative_parts else None

    if folder_name in PDF_COLLECTIONS:
        collection_meta = PDF_COLLECTIONS[folder_name]
    elif include_unknown:
        folder_name = folder_name or "Unknown"
        collection_meta = {
            "vendor": "unknown",
            "product": "unknown",
            "collection_name": folder_name,
            "source_type": "pdf",
            "source_group": "uncategorized",
            "priority": 3,
            "public_or_sanitized": "unknown",
        }
    else:
        return folder_name, None

    component, document_family = infer_pdf_component_and_family(
        filename=pdf_path.name,
        folder_name=folder_name,
    )

    return folder_name, {
        **collection_meta,
        "folder_origin": folder_name,
        "component": component,
        "document_family": document_family,
        "title": infer_title(pdf_path),
    }


def discover_pdfs(pdf_dir: Path) -> list[Path]:
    return sorted(pdf_dir.rglob("*.pdf"))


def load_pdf_documents(pdf_dir: Path, include_unknown: bool = False) -> tuple[list[Any], BuildStats, list[str]]:
    stats = BuildStats()
    docs = []
    skipped = []

    pdf_files = discover_pdfs(pdf_dir)
    stats.pdf_files_found = len(pdf_files)

    for pdf_path in pdf_files:
        folder_name, metadata = get_pdf_collection_metadata(pdf_path, pdf_dir, include_unknown=include_unknown)
        if metadata is None:
            skipped.append(str(pdf_path))
            stats.pdf_files_skipped += 1
            continue

        try:
            loader = PyPDFLoader(str(pdf_path))
            loaded_pages = loader.load()
        except Exception as exc:
            skipped.append(f"{pdf_path} :: {type(exc).__name__}: {exc}")
            stats.pdf_files_skipped += 1
            continue

        stats.pdf_files_loaded += 1
        stats.pages_loaded += len(loaded_pages)

        for page_doc in loaded_pages:
            page_doc.metadata.update(metadata)
            page_doc.metadata["source"] = str(pdf_path)
            page_doc.metadata["source_name"] = pdf_path.name
            page_doc.metadata["canonical_url"] = page_doc.metadata.get("source")
            page_doc.metadata["domain"] = "local_pdf"
            page_doc.metadata["seed_origin"] = "local_pdf"

            # PyPDFLoader usually provides zero-based page. Add a user-facing label.
            page = page_doc.metadata.get("page")
            if page is not None and "page_label" not in page_doc.metadata:
                try:
                    page_doc.metadata["page_label"] = str(int(page) + 1)
                except Exception:
                    page_doc.metadata["page_label"] = str(page)

            docs.append(page_doc)

    return docs, stats, skipped


def build_vectorstore(
    docs: list[Any],
    output_dir: Path,
    embedding_model_name: str,
    chunk_size: int,
    chunk_overlap: int,
    collection_name: str,
) -> tuple[Any, list[Any]]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    chunks = splitter.split_documents(docs)

    embedding_model = HuggingFaceEmbeddings(model_name=embedding_model_name)

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embedding_model,
        collection_name=collection_name,
        persist_directory=str(output_dir),
    )

    # Chroma persists automatically in recent versions; call persist if available.
    if hasattr(vectorstore, "persist"):
        try:
            vectorstore.persist()
        except Exception:
            pass

    return vectorstore, chunks


def write_manifest(
    output_dir: Path,
    args: argparse.Namespace,
    stats: BuildStats,
    chunks_count: int,
    skipped: list[str],
) -> Path:
    manifest = {
        "created_at": datetime.now().isoformat(),
        "pdf_dir": str(Path(args.pdf_dir).resolve()),
        "output_dir": str(output_dir.resolve()),
        "collection_name": args.collection_name,
        "embedding_model_name": args.embedding_model,
        "chunk_size": args.chunk_size,
        "chunk_overlap": args.chunk_overlap,
        "include_unknown": args.include_unknown,
        "stats": {
            "pdf_files_found": stats.pdf_files_found,
            "pdf_files_loaded": stats.pdf_files_loaded,
            "pdf_files_skipped": stats.pdf_files_skipped,
            "pages_loaded": stats.pages_loaded,
            "chunks_created": chunks_count,
        },
        "skipped": skipped,
        "known_collections": PDF_COLLECTIONS,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "build_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Arus PrintAssist Chroma vectorstore from PDF folders.")
    parser.add_argument("--pdf-dir", default="knowledge_base_pdfs", help="Root folder containing PDF collections.")
    parser.add_argument("--output-dir", default="vectorstore/chroma", help="Chroma persistence directory to create/update.")
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL, help="HuggingFace embedding model name.")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE, help="Chunk size for text splitting.")
    parser.add_argument("--chunk-overlap", type=int, default=DEFAULT_CHUNK_OVERLAP, help="Chunk overlap for text splitting.")
    parser.add_argument("--collection-name", default=DEFAULT_COLLECTION_NAME, help="Chroma collection name. Must match app config if customized.")
    parser.add_argument("--include-unknown", action="store_true", help="Include PDFs outside known collection folders with unknown metadata.")
    parser.add_argument("--force", action="store_true", help="Delete output dir before rebuilding if it already exists.")
    parser.add_argument("--dry-run", action="store_true", help="Only discover/load metadata, do not build embeddings/vectorstore.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    pdf_dir = Path(args.pdf_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()

    if not pdf_dir.exists():
        print(f"[ERROR] PDF directory not found: {pdf_dir}", file=sys.stderr)
        return 2

    if output_dir.exists() and args.force and not args.dry_run:
        shutil.rmtree(output_dir)

    if output_dir.exists() and any(output_dir.iterdir()) and not args.force and not args.dry_run:
        print(f"[ERROR] Output directory already exists and is not empty: {output_dir}", file=sys.stderr)
        print("        Use --force or choose a new --output-dir.", file=sys.stderr)
        return 2

    print("[INFO] PDF directory:", pdf_dir)
    print("[INFO] Output directory:", output_dir)
    print("[INFO] Embedding model:", args.embedding_model)
    print("[INFO] Chunk size/overlap:", args.chunk_size, args.chunk_overlap)

    docs, stats, skipped = load_pdf_documents(pdf_dir, include_unknown=args.include_unknown)

    print("[INFO] PDF files found:", stats.pdf_files_found)
    print("[INFO] PDF files loaded:", stats.pdf_files_loaded)
    print("[INFO] PDF files skipped:", stats.pdf_files_skipped)
    print("[INFO] Pages loaded:", stats.pages_loaded)

    if skipped:
        print("[WARN] Skipped PDFs:")
        for item in skipped[:20]:
            print("  -", item)
        if len(skipped) > 20:
            print(f"  ... {len(skipped) - 20} more")

    if not docs:
        print("[ERROR] No documents loaded. Check folder structure and PDFs.", file=sys.stderr)
        return 2

    if args.dry_run:
        print("[INFO] Dry run complete. No vectorstore created.")
        return 0

    vectorstore, chunks = build_vectorstore(
        docs=docs,
        output_dir=output_dir,
        embedding_model_name=args.embedding_model,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        collection_name=args.collection_name,
    )

    stats.chunks_created = len(chunks)
    manifest_path = write_manifest(output_dir, args, stats, len(chunks), skipped)

    print("[OK] Vectorstore built successfully.")
    print("[OK] Output directory:", output_dir)
    print("[OK] Chunks indexed:", len(chunks))
    print("[OK] Manifest:", manifest_path)
    print("\nNext step: update app/config.py CONFIG['vectorstore_dir'] to:")
    print(str(output_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
